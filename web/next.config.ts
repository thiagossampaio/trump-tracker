import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Fixa a raiz do workspace neste diretório. Sem isso, um package-lock.json
  // solto no diretório pai (monorepo Python) faz o Turbopack inferir a raiz
  // errada e observar a árvore inteira, causando recompilações/reloads em loop.
  turbopack: {
    root: path.resolve(__dirname),
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "t3.gstatic.com",
      },
    ],
  },
};

export default nextConfig;
