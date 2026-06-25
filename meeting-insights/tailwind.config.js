/** Tailwind config — builds a static CSS so the app has no runtime CDN dependency. */
module.exports = {
  content: ["./frontend/**/*.{html,js}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff", 100: "#dbe6ff", 500: "#3b5bdb",
          600: "#2f49b0", 700: "#27408b", 900: "#1a2b5c",
        },
        mbs: "#3b5bdb",
        mcorp: "#f08c00",
      },
    },
  },
  plugins: [],
};
