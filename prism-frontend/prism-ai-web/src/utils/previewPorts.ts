/**
 * Preview Port Utilities
 * Matches the deterministic port assignment logic in ships-backend/app/services/preview_manager.py
 */

const BASE_PORT = 5200;
const MAX_INSTANCES = 50;

/**
 * Calculate CRC32 checksum of a string
 */
function crc32(str: string): number {
    // Wrapper for consistency if we want to swap implementation later
    return getCRC32(str);
}

// Better approach:
// Use a standard CRC-32 table
const makeCRCTable = () => {
  let c;
  const crcTable = [];
  for(let n =0; n < 256; n++){
    c = n;
    for(let k =0; k < 8; k++){
      c = ((c&1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
    }
    crcTable[n] = c;
  }
  return crcTable;
}

const crcTable = makeCRCTable();

const getCRC32 = (str: string) => {
  let crc = 0 ^ (-1);
  for (let i = 0; i < str.length; i++ ) {
    crc = (crc >>> 8) ^ crcTable[(crc ^ str.charCodeAt(i)) & 0xFF];
  }
  return (crc ^ (-1)) >>> 0;
};

/**
 * Get the deterministic port for a given Run ID
 * @param runId 
 * @returns Port number (5200-5249)
 */
export const getDeterministicPort = (runId: string): number => {
    if (!runId) return BASE_PORT;
    
    // In Python: zlib.crc32(run_id.encode('utf-8'))
    // This JS implementation matches standard CRC32.
    const hash = getCRC32(runId);
    
    const offset = hash % MAX_INSTANCES;
    return BASE_PORT + offset;
};
