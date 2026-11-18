// A synthetic Moroccan RIB, unique per test run, with a valid control key, so a reused stack does not
// refuse the bank account as already registered (D-23). The key follows avenel.bank.rib
// (key = modulus - (prefix x 100 mod modulus)); the modulus is read by the API from the jurisdiction pack
// (identifiers.rib.modulus), so a wrong value here would make the API reject the RIB, not accept a bad one.
const RIB_MODULUS = 97n;

export function freshRib(bankPrefix = '0077800'): string {
  const unique = `${Date.now()}${Math.floor(Math.random() * 100)}`.padStart(15, '0').slice(-15);
  const prefix = `${bankPrefix}${unique}`;
  const key = RIB_MODULUS - ((BigInt(prefix) * 100n) % RIB_MODULUS);
  return `${prefix}${key.toString().padStart(2, '0')}`;
}
