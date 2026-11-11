// Preview the same static output deployed to Pages, without loading Start's SSR handler.
export default {
  base: process.env.VITE_BASE_PATH || '/nri-future-risk/',
  publicDir: false,
  build: { outDir: 'dist' },
};
