/**
 * The AI output contract version this console is built against.
 *
 * One constant, because three hard-coded copies (sidebar, landing nav, landing
 * footer) all still read 1.2.0 after the contract moved to 1.3.0, when `mask`
 * became a real polygon. Bump it here together with ai/ghostnet/contract.py's
 * CONTRACT_VERSION and the docs/HANDOFF.md entry.
 */
export const CONTRACT_VERSION = "1.3.0";
