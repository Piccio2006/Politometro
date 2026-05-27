-- Politometro: viste e query per correlazioni aggregate.
-- Usare solo su sessioni con research_consent = true e mai per targeting individuale.

create or replace view consented_profiles as
select
  s.id as session_id,
  s.created_at,
  s.mode,
  s.age_range,
  s.education,
  s.origin_area,
  s.political_interest,
  s.political_knowledge,
  s.news_frequency,
  s.student_worker,
  r.confidence,
  r.self_coherence,
  r.reliability_score,
  r.reliability_label,
  r.ideology_name,
  r.top_party_name,
  r.top_historical_name,
  r.nemesis_name,
  r.economy,
  r.authority,
  r.culture,
  r.geopolitics,
  r.environment,
  r.technology,
  r.equality,
  r.justice
from quiz_sessions s
join result_profiles r on r.session_id = s.id
where s.research_consent = true
  and s.deleted_at is null;

create or replace view daily_profile_trends as
select
  date_trunc('day', created_at)::date as day,
  count(*) as samples,
  avg(confidence) as avg_confidence,
  avg(self_coherence) as avg_self_coherence,
  avg(reliability_score) as avg_reliability,
  avg(economy) as avg_economy,
  avg(authority) as avg_authority,
  avg(culture) as avg_culture,
  avg(geopolitics) as avg_geopolitics,
  avg(environment) as avg_environment,
  avg(technology) as avg_technology,
  avg(equality) as avg_equality,
  avg(justice) as avg_justice
from consented_profiles
group by 1
order by 1;

create or replace view dataset_health_summary as
select
  count(*) as consented_samples,
  count(*) filter (where mode = 'social') as social_samples,
  count(*) filter (where mode = 'quick') as quick_samples,
  count(*) filter (where mode = 'deep') as deep_samples,
  avg(confidence) as avg_confidence,
  avg(self_coherence) as avg_self_coherence,
  avg(reliability_score) as avg_reliability,
  count(*) filter (where education is not null and education <> '') as education_filled,
  count(*) filter (where age_range is not null and age_range <> '') as age_filled,
  case
    when count(*) >= 1000 then 'scala'
    when count(*) >= 300 then 'validazione'
    when count(*) >= 100 then 'beta'
    when count(*) >= 30 then 'early'
    else 'setup'
  end as dataset_stage
from consented_profiles;

create or replace view demographic_profile_summary as
select
  'education' as field,
  education as value,
  count(*) as samples,
  avg(confidence) as avg_confidence,
  avg(self_coherence) as avg_self_coherence,
  avg(reliability_score) as avg_reliability,
  avg(economy) as economy,
  avg(authority) as authority,
  avg(culture) as culture,
  avg(geopolitics) as geopolitics,
  avg(environment) as environment,
  avg(technology) as technology,
  avg(equality) as equality,
  avg(justice) as justice
from consented_profiles
where education is not null and education <> ''
group by education
union all
select
  'age_range',
  age_range,
  count(*),
  avg(confidence),
  avg(self_coherence),
  avg(reliability_score),
  avg(economy),
  avg(authority),
  avg(culture),
  avg(geopolitics),
  avg(environment),
  avg(technology),
  avg(equality),
  avg(justice)
from consented_profiles
where age_range is not null and age_range <> ''
group by age_range
union all
select
  'political_knowledge',
  political_knowledge,
  count(*),
  avg(confidence),
  avg(self_coherence),
  avg(reliability_score),
  avg(economy),
  avg(authority),
  avg(culture),
  avg(geopolitics),
  avg(environment),
  avg(technology),
  avg(equality),
  avg(justice)
from consented_profiles
where political_knowledge is not null and political_knowledge <> ''
group by political_knowledge;

-- Distribuzione dei risultati principali per gruppi facoltativi.
-- La soglia protegge dall'interpretazione di micro-gruppi troppo piccoli.
create or replace view demographic_party_summary as
select
  'education' as field,
  education as value,
  top_party_name,
  ideology_name,
  count(*) as samples,
  avg(confidence) as avg_confidence,
  avg(self_coherence) as avg_self_coherence,
  avg(reliability_score) as avg_reliability
from consented_profiles
where education is not null and education <> ''
group by education, top_party_name, ideology_name
having count(*) >= 30
union all
select
  'age_range',
  age_range,
  top_party_name,
  ideology_name,
  count(*),
  avg(confidence),
  avg(self_coherence),
  avg(reliability_score)
from consented_profiles
where age_range is not null and age_range <> ''
group by age_range, top_party_name, ideology_name
having count(*) >= 30
union all
select
  'political_knowledge',
  political_knowledge,
  top_party_name,
  ideology_name,
  count(*),
  avg(confidence),
  avg(self_coherence),
  avg(reliability_score)
from consented_profiles
where political_knowledge is not null and political_knowledge <> ''
group by political_knowledge, top_party_name, ideology_name
having count(*) >= 30;

create or replace view feedback_accuracy_summary as
select
  f.predicted_ideology,
  party.predicted_party,
  count(*) as samples,
  avg(f.accuracy_rating) as avg_accuracy_rating
from feedback f
join quiz_sessions s on s.id = f.session_id
cross join lateral unnest(coalesce(f.predicted_parties, array[]::text[])) as party(predicted_party)
where s.feedback_consent = true
  and s.deleted_at is null
  and f.accuracy_rating is not null
group by f.predicted_ideology, party.predicted_party
having count(*) >= 30
order by samples desc, avg_accuracy_rating desc;

create or replace view support_contact_pipeline as
select
  status,
  topic,
  count(*) as contacts,
  min(created_at) as first_contact_at,
  max(created_at) as last_contact_at
from support_contacts
where consent_contact = true
group by status, topic
order by contacts desc, last_contact_at desc;

create or replace view question_response_summary as
select
  a.question_id,
  count(*) as samples,
  avg(a.answer_value) as avg_answer,
  stddev_pop(a.answer_value) as sd_answer,
  corr(a.answer_value::numeric, r.economy) as corr_economy,
  corr(a.answer_value::numeric, r.authority) as corr_authority,
  corr(a.answer_value::numeric, r.culture) as corr_culture,
  corr(a.answer_value::numeric, r.geopolitics) as corr_geopolitics,
  corr(a.answer_value::numeric, r.environment) as corr_environment,
  corr(a.answer_value::numeric, r.technology) as corr_technology,
  corr(a.answer_value::numeric, r.equality) as corr_equality,
  corr(a.answer_value::numeric, r.justice) as corr_justice
from answers a
join quiz_sessions s on s.id = a.session_id
join result_profiles r on r.session_id = s.id
where s.research_consent = true
  and s.deleted_at is null
group by a.question_id;

-- Query utile: segnali forti da controllare, non da usare automaticamente.
-- Soglia minima: almeno 100 risposte sulla domanda.
create or replace view strongest_question_axis_signals as
select *
from question_response_summary
where samples >= 100
order by greatest(
  abs(coalesce(corr_economy, 0)),
  abs(coalesce(corr_authority, 0)),
  abs(coalesce(corr_culture, 0)),
  abs(coalesce(corr_geopolitics, 0)),
  abs(coalesce(corr_environment, 0)),
  abs(coalesce(corr_technology, 0)),
  abs(coalesce(corr_equality, 0)),
  abs(coalesce(corr_justice, 0))
) desc;

-- Query diagnostica: assi più instabili o potenzialmente biasati per gruppo.
-- Non va usata per targeting politico; serve a correggere domande e modello.
create or replace view demographic_axis_deviation_flags as
with global_avg as (
  select
    avg(economy) as economy,
    avg(authority) as authority,
    avg(culture) as culture,
    avg(geopolitics) as geopolitics,
    avg(environment) as environment,
    avg(technology) as technology,
    avg(equality) as equality,
    avg(justice) as justice
  from consented_profiles
),
groups as (
  select *
  from demographic_profile_summary
  where samples >= 50
)
select
  groups.field,
  groups.value,
  groups.samples,
  groups.economy - global_avg.economy as economy_delta,
  groups.authority - global_avg.authority as authority_delta,
  groups.culture - global_avg.culture as culture_delta,
  groups.geopolitics - global_avg.geopolitics as geopolitics_delta,
  groups.environment - global_avg.environment as environment_delta,
  groups.technology - global_avg.technology as technology_delta,
  groups.equality - global_avg.equality as equality_delta,
  groups.justice - global_avg.justice as justice_delta
from groups
cross join global_avg
order by greatest(
  abs(groups.economy - global_avg.economy),
  abs(groups.authority - global_avg.authority),
  abs(groups.culture - global_avg.culture),
  abs(groups.geopolitics - global_avg.geopolitics),
  abs(groups.environment - global_avg.environment),
  abs(groups.technology - global_avg.technology),
  abs(groups.equality - global_avg.equality),
  abs(groups.justice - global_avg.justice)
) desc;
