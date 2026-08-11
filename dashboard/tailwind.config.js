/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    // Tremor's own components must be scanned so their classes aren't purged.
    "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
  ],
  // tremor dựng class màu cho chart bằng chuỗi runtime (vd `fill-yellow-500`) từ prop `colors`.
  // Tailwind JIT chỉ sinh CSS cho class NÓ THẤY trong source lúc build — các class màu dựng động từ
  // dữ liệu DB không xuất hiện trong source nên bị bỏ → cột ra MÀU ĐEN. safelist ép sinh sẵn các
  // class fill/stroke/bg/text/border cho đúng bảng màu chart dùng (BRAND_COLOR trong Dashboard.tsx).
  safelist: [
    {
      pattern:
        /^(fill|stroke|bg|text|border)-(yellow|red|purple|green|blue|orange|cyan|lime|pink|indigo)-(100|300|500|700)$/,
    },
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
