import { createClient } from '@supabase/supabase-js';
import fs from 'fs/promises';

const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function main() {
  const exampleStr = await fs.readFile('../../config/generated/calibration_runs_row.example.json', 'utf8');
  const exampleData = JSON.parse(exampleStr);

  // Attempt to authenticate first so we execute as 'authenticated', not 'anon'
  console.log("Attempting to authenticate as test user...");
  let { data: authData, error: authErr } = await supabase.auth.signUp({
    email: 'test_robocop@example.com',
    password: 'TestPassword123!'
  });
  
  if (authErr && authErr.message.includes('already registered')) {
    const res = await supabase.auth.signInWithPassword({
      email: 'test_robocop@example.com',
      password: 'TestPassword123!'
    });
    authData = res.data;
    authErr = res.error;
  }

  if (authErr) {
    console.error("Auth Error:", authErr.message);
    // Continue anyway to see if table is accessible 
  } else {
    console.log("Authenticated as:", authData.user?.id);
  }

  const { data, error } = await supabase
    .from('calibration_runs')
    .insert([exampleData])
    .select();

  if (error) {
    console.error('Insert Error:', error);
  } else {
    console.log('Inserted:', data);
  }
}

main().catch(console.error);
