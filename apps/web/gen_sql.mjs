import fs from 'fs/promises';

async function main() {
  const exampleStr = await fs.readFile('../../config/generated/calibration_runs_row.example.json', 'utf8');
  const d = JSON.parse(exampleStr);

  const sql = `
INSERT INTO public.calibration_runs (
  run_id, canonical_run_label, run_timestamp, run_timestamp_utc, registry_recorded_at, 
  status, job_name, hypothesis, job_version, campaign, policy_name, policy_path, 
  manifest_name, manifest_path, optimization_strategy, target_scope, param_scope,
  aggregate_score, mean_final_loss, mean_improvement_pct, best_case, worst_case, 
  case_count, run_dir, artifact_manifest_path, tags, job_metadata, parameter_classes,
  target_scopes, param_scopes, trace_context, chat_context, artifact_refs
) VALUES (
  '${d.run_id}', '${d.canonical_run_label}', '${d.run_timestamp}', '${d.run_timestamp_utc}', '${d.registry_recorded_at}',
  '${d.status}', ${d.job_name ? `'${d.job_name}'` : 'null'}, ${d.hypothesis ? `'${d.hypothesis}'` : 'null'}, ${d.job_version ? d.job_version : 'null'}, ${d.campaign ? `'${d.campaign}'` : 'null'}, '${d.policy_name}', ${d.policy_path ? `'${d.policy_path}'` : 'null'},
  '${d.manifest_name}', ${d.manifest_path ? `'${d.manifest_path}'` : 'null'}, '${d.optimization_strategy}', '${d.target_scope}', '${d.param_scope}',
  ${d.aggregate_score}, ${d.mean_final_loss}, ${d.mean_improvement_pct}, '${d.best_case}', '${d.worst_case}',
  ${d.case_count}, '${d.run_dir.replace(/\\/g, '\\\\')}', '${d.artifact_manifest_path.replace(/\\/g, '\\\\')}', '${JSON.stringify(d.tags)}'::jsonb, '${JSON.stringify(d.job_metadata)}'::jsonb, ${d.parameter_classes ? `'${JSON.stringify(d.parameter_classes)}'::jsonb` : 'null'},
  '${JSON.stringify(d.target_scopes)}'::jsonb, '${JSON.stringify(d.param_scopes)}'::jsonb, '${JSON.stringify(d.trace_context)}'::jsonb, '${JSON.stringify(d.chat_context).replace(/'/g, "''")}'::jsonb, '${JSON.stringify(d.artifact_refs).replace(/\\/g, '\\\\')}'::jsonb
);
  `;
  await fs.writeFile('insert.sql', sql.trim());
  console.log('Saved insert.sql');
}

main();
