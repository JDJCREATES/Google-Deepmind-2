/**
 * Tabs Component
 * 
 * Reusable tab switcher with keyboard navigation and accessibility support.
 * 
 * @module components/common/Tabs
 */

import { useState, useRef, useEffect } from 'react';
import './Tabs.css';

/**
 * Tab item definition
 */
export interface Tab {
  /** Unique identifier */
  id: string;
  /** Display label */
  label: string;
  /** Optional icon */
  icon?: React.ReactNode;
  /** Disabled state */
  disabled?: boolean;
}

/**
 * Tabs component props
 */
export interface TabsProps {
  /** Array of tabs to display */
  tabs: Tab[];
  /** Currently active tab ID */
  activeTab: string;
  /** Callback when tab changes */
  onTabChange: (tabId: string) => void;
  /** Optional CSS class name */
  className?: string;
  /** Orientation */
  orientation?: 'horizontal' | 'vertical';
}

/**
 * Tabs Component
 * 
 * Accessible tab switcher with keyboard navigation support.
 * Follows WAI-ARIA tab pattern.
 * 
 * @example
 * ```tsx
 * <Tabs
 *   tabs={[
 *     { id: 'files', label: 'Files', icon: <FileIcon /> },
 *     { id: 'artifacts', label: 'Artifacts', icon: <ArtifactIcon /> }
 *   ]}
 *   activeTab={activeTab}
 *   onTabChange={setActiveTab}
 * />
 * ```
 */
export default function Tabs({
  tabs,
  activeTab,
  onTabChange,
  className = '',
  orientation = 'horizontal',
}: TabsProps) {
  const tablistRef = useRef<HTMLDivElement>(null);
  const [focusedIndex, setFocusedIndex] = useState(0);

  // Find active tab index
  const activeIndex = tabs.findIndex(tab => tab.id === activeTab);

  // Update focused index when active changes
  useEffect(() => {
    if (activeIndex !== -1) {
      setFocusedIndex(activeIndex);
    }
  }, [activeIndex]);

  /**
   * Handle keyboard navigation
   */
  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = index;

    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        e.preventDefault();
        nextIndex = (index + 1) % tabs.length;
        while (tabs[nextIndex].disabled && nextIndex !== index) {
          nextIndex = (nextIndex + 1) % tabs.length;
        }
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        e.preventDefault();
        nextIndex = (index - 1 + tabs.length) % tabs.length;
        while (tabs[nextIndex].disabled && nextIndex !== index) {
          nextIndex = (nextIndex - 1 + tabs.length) % tabs.length;
        }
        break;
      case 'Home':
        e.preventDefault();
        nextIndex = 0;
        while (tabs[nextIndex].disabled && nextIndex < tabs.length - 1) {
          nextIndex++;
        }
        break;
      case 'End':
        e.preventDefault();
        nextIndex = tabs.length - 1;
        while (tabs[nextIndex].disabled && nextIndex > 0) {
          nextIndex--;
        }
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (!tabs[index].disabled) {
          onTabChange(tabs[index].id);
        }
        return;
      default:
        return;
    }

    // Focus the tab button
    const buttons = tablistRef.current?.querySelectorAll('[role="tab"]');
    if (buttons && buttons[nextIndex]) {
      (buttons[nextIndex] as HTMLElement).focus();
      setFocusedIndex(nextIndex);
    }
  };

  return (
    <div
      className={`tabs ${orientation} ${className}`}
      role="tablist"
      aria-orientation={orientation}
      ref={tablistRef}
    >
      {tabs.map((tab, index) => (
        <button
          key={tab.id}
          role="tab"
          id={`tab-${tab.id}`}
          aria-selected={tab.id === activeTab}
          aria-controls={`tabpanel-${tab.id}`}
          aria-disabled={tab.disabled}
          tabIndex={tab.id === activeTab ? 0 : -1}
          className={`tab ${tab.id === activeTab ? 'active' : ''} ${
            tab.disabled ? 'disabled' : ''
          }`}
          onClick={() => {
            if (!tab.disabled) {
              onTabChange(tab.id);
            }
          }}
          onKeyDown={(e) => handleKeyDown(e, index)}
          disabled={tab.disabled}
        >
          {tab.icon && <span className="tab-icon">{tab.icon}</span>}
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
    </div>
  );
}
