/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  // Ensure axios is bundled correctly
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Client-side: exclude Node.js modules and force browser build
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        http2: false,
        http: false,
        https: false,
        zlib: false,
        stream: false,
        url: false,
        util: false,
        buffer: false,
        crypto: false,
        os: false,
        path: false,
        querystring: false,
        child_process: false,
        dns: false,
        events: false,
        'node:http': false,
        'node:https': false,
        'node:http2': false,
        'node:net': false,
        'node:tls': false,
        'node:stream': false,
        'node:util': false,
        'node:url': false,
        'node:buffer': false,
        'node:crypto': false,
        'node:os': false,
        'node:path': false,
        'node:querystring': false,
        'node:zlib': false,
      };
      
      // Don't alias axios, let webpack handle it normally
    }
    
    return config;
  },
}

module.exports = nextConfig
