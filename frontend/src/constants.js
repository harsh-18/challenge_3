/**
 * Application-wide constants and configuration.
 * Centralizes magic strings, API paths, and category mappings.
 */

// API endpoint paths
export const API_PATHS = {
  ROOT: '/api',
  HEALTH: '/health',
  METRICS: '/api/metrics',
  LOGS: '/api/logs',
  LOGS_TEXT: '/api/logs/text',
  LOGS_RECEIPT: '/api/logs/receipt',
  CHAT: '/api/chat',
  TIPS: '/api/tips',
  INSIGHTS: '/api/insights',
};

// Carbon footprint categories
export const CATEGORIES = {
  TRANSIT: 'transit',
  ENERGY: 'energy',
  FOOD: 'food',
  WASTE: 'waste',
};

// Category display configuration
export const CATEGORY_CONFIG = {
  transit: { label: 'Travel', emoji: '🚗', color: 'var(--color-transit)' },
  energy: { label: 'Energy', emoji: '⚡', color: 'var(--color-energy)' },
  food: { label: 'Food', emoji: '🥗', color: 'var(--color-food)' },
  waste: { label: 'Waste', emoji: '♻️', color: 'var(--color-waste)' },
};

// File upload constraints
export const UPLOAD_CONFIG = {
  MAX_SIZE_MB: 8,
  ALLOWED_TYPES: ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'],
  ALLOWED_EXTENSIONS: 'JPG, PNG, WEBP, PDF',
};

// Chat suggestions for the Eco-Coach
export const CHAT_SUGGESTIONS = [
  'How can I reduce food emissions?',
  'Tips to lower my electricity bill?',
  'Is driving an EV actually eco-friendly?',
  'Recommend a green lifestyle habit.',
];

// Comparative carbon context (weekly averages in kg CO2e)
export const CARBON_BENCHMARKS = {
  global_weekly_kg: 133.0,
  india_weekly_kg: 36.5,
  eu_weekly_kg: 126.9,
};
