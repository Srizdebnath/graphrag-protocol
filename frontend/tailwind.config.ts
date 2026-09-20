import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      borderWidth: {
        "3": "3px",
        "4": "4px",
      },
      boxShadow: {
        "brutal-xs": "1px 1px 0px 0px #000000",
        "brutal-sm": "2px 2px 0px 0px #000000",
        "brutal": "4px 4px 0px 0px #000000",
        "brutal-lg": "6px 6px 0px 0px #000000",
        "brutal-xl": "8px 8px 0px 0px #000000",
      },
      colors: {
        brutal: {
          yellow: "#FFE600",
          pink: "#FF7675",
          blue: "#74B9FF",
          green: "#55EFC4",
          purple: "#A29BFE",
          orange: "#FAB1A0",
          bg: "#F7F5EE",
        },
      },
    },
  },
  plugins: [],
};
export default config;
