// Vitest counterpart of scripts/check_test_count.py: fails if fewer tests run than the baseline.
// Usage: vitest run --reporter=json --outputFile=.vitest-results.json && node this-script
import { readFileSync } from 'node:fs';
const baseline = Number(readFileSync('src/.test_count_baseline', 'utf8').trim());
const results = JSON.parse(readFileSync('.vitest-results.json', 'utf8'));
const passed = results.numPassedTests;
const total = results.numTotalTests;
console.log(`check_web_test_count: ${passed}/${total} passed, baseline ${baseline}`);
if (results.numFailedTests > 0 || passed < baseline) {
  console.error('check_web_test_count: below baseline or failures present; see TESTS_REMOVED.md');
  process.exit(1);
}
