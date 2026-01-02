/**
 * Typed OnsenUI Component Wrappers
 * 
 * React 18+ removed implicit children from React.FC, and react-onsenui types
 * haven't been updated. These wrappers provide properly typed versions of
 * OnsenUI components.
 * 
 * @see https://stackoverflow.com/questions/71788254/react-18-typescript-children-fc
 */

import React from 'react';
import * as Ons from 'react-onsenui';

// ─────────────────────────────────────────────────────────────
// Type Definitions
// ─────────────────────────────────────────────────────────────

export interface TypedToolbarProps {
  children?: React.ReactNode;
  modifier?: string;
  className?: string;
  style?: React.CSSProperties;
}

export interface TypedToolbarButtonProps {
  children?: React.ReactNode;
  modifier?: string;
  disabled?: boolean;
  onClick?: (event: React.MouseEvent<HTMLElement>) => void;
}

export interface TypedPageProps {
  children?: React.ReactNode;
  contentStyle?: React.CSSProperties;
  modifier?: string;
  renderToolbar?: () => React.ReactNode;
  renderBottomToolbar?: () => React.ReactNode;
  renderModal?: () => React.ReactNode;
  renderFixed?: () => React.ReactNode;
}

export interface TypedTabProps {
  label?: string;
  icon?: string;
  badge?: string | number;
  active?: boolean;
}

export interface TypedTabbarProps {
  index?: number;
  renderTabs?: () => Array<{ content: React.ReactNode; tab: React.ReactNode }>;
  position?: 'bottom' | 'top' | 'auto';
  swipeable?: boolean;
  onPreChange?: (event: { index: number; activeIndex: number }) => void;
  onPostChange?: (event: { index: number }) => void;
}

export interface TypedIconProps {
  icon?: string;
  size?: number | string;
  rotate?: number;
  fixedWidth?: boolean;
  spin?: boolean;
}

export interface TypedSwitchProps {
  checked?: boolean;
  disabled?: boolean;
  modifier?: string;
  inputId?: string;
  onChange?: (event: { target: { checked: boolean } | null; value: boolean }) => void;
}

// ─────────────────────────────────────────────────────────────
// Component Wrappers - Cast to properly typed versions
// ─────────────────────────────────────────────────────────────

export const Toolbar = Ons.Toolbar as unknown as React.FC<TypedToolbarProps>;
export const ToolbarButton = Ons.ToolbarButton as unknown as React.FC<TypedToolbarButtonProps>;
export const Page = Ons.Page as unknown as React.FC<TypedPageProps>;
export const Tab = Ons.Tab as unknown as React.FC<TypedTabProps>;
export const Tabbar = Ons.Tabbar as unknown as React.FC<TypedTabbarProps>;
export const Icon = Ons.Icon as unknown as React.FC<TypedIconProps>;
export const Switch = Ons.Switch as unknown as React.FC<TypedSwitchProps>;

// Re-export other components that don't have children issues
export { AlertDialog, AlertDialogButton, Button, Card, Checkbox, Fab, Input, List, ListItem, Modal, Navigator, Popover, ProgressBar, ProgressCircular, Radio, Range, Ripple, SearchInput, Segment, Select, SpeedDial, SpeedDialItem, Splitter, SplitterContent, SplitterSide, Toast } from 'react-onsenui';
