// NEXT_DIST lets parallel builds use separate output dirs (e.g. NEXT_DIST=.next-qa).
module.exports = { distDir: process.env.NEXT_DIST || ".next", poweredByHeader: false };
