/**
 * Timeline Demo Data
 * 
 * Sample data for testing the timeline UI
 */

import { TimelineNode } from '../types/timeline';

export const demoTimelineNodes: TimelineNode[] = [
  {
    id: 'node-1',
    type: 'feature',
    status: 'success',
    title: 'Init',
    description: 'Project initialization',
    timestamp: new Date(Date.now() - 3600000 * 10),
    duration_ms: 15000,
    files_changed: ['package.json', 'tsconfig.json', 'vite.config.ts'],
    lines_added: 120,
    lines_removed: 0,
    agents_used: ['Coder'],
    phases: [
      { name: 'Planning', status: 'success', duration_ms: 5000 },
      { name: 'Coding', status: 'success', duration_ms: 8000 },
      { name: 'Validating', status: 'success', duration_ms: 2000 }
    ],
    issues_fixed: []
  },
  {
    id: 'node-2',
    type: 'feature',
    status: 'success',
    title: 'Auth',
    description: 'Authentication system',
    timestamp: new Date(Date.now() - 3600000 * 8),
    duration_ms: 154000,
    files_changed: ['src/components/AuthModal.tsx', 'src/lib/auth.ts', 'src/types/user.ts'],
    lines_added: 245,
    lines_removed: 12,
    agents_used: ['Coder', 'Validator'],
    phases: [
      { name: 'Planning', status: 'success', duration_ms: 20000 },
      { name: 'Coding', status: 'success', duration_ms: 120000 },
      { name: 'Validating', status: 'success', duration_ms: 14000 }
    ],
    issues_fixed: [
      { pitfall_id: 'missing-error-handling', auto_fixed: true, description: 'Missing error handling' }
    ]
  },
  {
    id: 'node-3',
    type: 'feature',
    status: 'success',
    title: 'Login',
    description: 'Login form component',
    timestamp: new Date(Date.now() - 3600000 * 6),
    duration_ms: 94000,
    files_changed: ['src/components/LoginForm.tsx', 'src/app/api/auth/route.ts'],
    lines_added: 127,
    lines_removed: 8,
    agents_used: ['Coder', 'Validator', 'Fixer'],
    phases: [
      { name: 'Planning', status: 'success', duration_ms: 15000 },
      { name: 'Coding', status: 'success', duration_ms: 60000 },
      { name: 'Validating', status: 'success', duration_ms: 19000 }
    ],
    issues_fixed: [
      { pitfall_id: 'import-path', auto_fixed: true, description: 'Import path correction' }
    ]
  },
  {
    id: 'node-4',
    type: 'feature',
    status: 'success',
    title: 'Dashboard',
    description: 'Main dashboard view',
    timestamp: new Date(Date.now() - 3600000 * 4),
    duration_ms: 180000,
    files_changed: [
      'src/components/Dashboard.tsx',
      'src/components/Sidebar.tsx',
      'src/lib/api.ts'
    ],
    lines_added: 312,
    lines_removed: 45,
    agents_used: ['Coder', 'Validator'],
    phases: [
      { name: 'Planning', status: 'success', duration_ms: 25000 },
      { name: 'Coding', status: 'success', duration_ms: 140000 },
      { name: 'Validating', status: 'success', duration_ms: 15000 }
    ],
    issues_fixed: []
  },
  {
    id: 'node-5',
    type: 'feature',
    status: 'warning',
    title: 'Search',
    description: 'Search functionality',
    timestamp: new Date(Date.now() - 3600000 * 2),
    duration_ms: 125000,
    files_changed: ['src/components/SearchBar.tsx', 'src/lib/search.ts'],
    lines_added: 156,
    lines_removed: 23,
    agents_used: ['Coder', 'Validator'],
    phases: [
      { name: 'Planning', status: 'success', duration_ms: 18000 },
      { name: 'Coding', status: 'success', duration_ms: 95000 },
      { name: 'Validating', status: 'success', duration_ms: 12000 }
    ],
    issues_fixed: [
      { pitfall_id: 'type-error', auto_fixed: false, description: 'TypeScript type error (manual fix)' }
    ]
  },
  {
    id: 'node-6',
    type: 'feature',
    status: 'in-progress',
    title: 'Dark Mode',
    description: 'Dark mode toggle',
    timestamp: new Date(),
    duration_ms: 45000,
    files_changed: ['src/components/ThemeToggle.tsx', 'src/styles/theme.css'],
    lines_added: 0,
    lines_removed: 0,
    agents_used: ['Coder'],
    phases: [
      { name: 'Planning', status: 'success', duration_ms: 15000 },
      { name: 'Coding', status: 'in-progress', duration_ms: 30000 },
      { name: 'Validating', status: 'pending', duration_ms: 0 }
    ],
    issues_fixed: []
  },
  {
    id: 'node-7',
    type: 'feature',
    status: 'pending',
    title: 'Deploy',
    description: 'Deployment configuration',
    timestamp: new Date(),
    duration_ms: 0,
    files_changed: [],
    lines_added: 0,
    lines_removed: 0,
    agents_used: [],
    phases: [],
    issues_fixed: []
  }
];
