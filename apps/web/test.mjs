import { getCalibrationRuns } from './lib/api/calibration-runs.mjs';

async function main() {
  const runs = await getCalibrationRuns();
  console.log('Result:', JSON.stringify(runs, null, 2));
}

main().catch(console.error);
