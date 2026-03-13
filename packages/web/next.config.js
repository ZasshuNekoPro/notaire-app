/** @type {import('next').NextConfig} */
const nextConfig = {
  // Configuration pour Docker standalone
  output: 'standalone',

  // Debug mode pour investigation SSR
  logging: {
    fetches: {
      fullUrl: true,
    },
  },

  // Configuration des variables d'environnement
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },

  // Configuration ESLint
  eslint: {
    // Attention: Cela permet aux builds de production de terminer avec succès même si
    // votre projet a des erreurs ESLint.
    ignoreDuringBuilds: true,
  },

  // Configuration TypeScript
  typescript: {
    // Attention: Cela permet aux builds de production de terminer avec succès même si
    // votre projet a des erreurs de type TypeScript.
    ignoreBuildErrors: true,
  },

  // Images externes autorisées
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },

  // Configuration expérimentale
  experimental: {
    // Performance optimizations
    turbo: {
      rules: {
        '*.svg': {
          loaders: ['@svgr/webpack'],
          as: '*.js',
        },
      },
    },
  },
}

module.exports = nextConfig