/**
 * Module augmentation for react-onsenui
 * 
 * React 18+ removed implicit children from React.FC.
 * react-onsenui types haven't been updated, so we need to augment them.
 * 
 * @see https://stackoverflow.com/questions/71788254/react-18-typescript-children-fc
 */

import 'react-onsenui';

declare module 'react-onsenui' {
  // Augment Toolbar to accept children
  export interface ToolbarProps {
    children?: React.ReactNode;
    modifier?: string;
    className?: string;
    style?: React.CSSProperties;
    id?: string;
  }

  // Augment ToolbarButton to accept children
  export interface ToolbarButtonProps {
    children?: React.ReactNode;
    modifier?: string;
    disabled?: boolean;
    onClick?: (event: React.MouseEvent<HTMLElement>) => void;
  }

  // Augment Page to accept children
  export interface PageProps {
    children?: React.ReactNode;
    contentStyle?: React.CSSProperties;
    modifier?: string;
    renderToolbar?: () => React.ReactNode;
    renderBottomToolbar?: () => React.ReactNode;
    renderModal?: () => React.ReactNode;
    renderFixed?: () => React.ReactNode;
    onInit?: () => void;
    onShow?: () => void;
    onHide?: () => void;
    onInfiniteScroll?: (done: () => void) => void;
  }

  // Augment Tab 
  export interface TabProps {
    children?: React.ReactNode;
    label?: string;
    icon?: string;
    badge?: string | number;
    active?: boolean;
  }

  // Augment Tabbar to accept children  
  export interface TabbarProps {
    children?: React.ReactNode;
    index?: number;
    renderTabs?: () => Array<{ content: React.ReactNode; tab: React.ReactNode }>;
    position?: 'bottom' | 'top' | 'auto';
    swipeable?: boolean;
    ignoreEdgeWidth?: number;
    animation?: 'none' | 'slide' | 'fade';
    animationOptions?: object;
    tabBorder?: boolean;
    onPreChange?: (event: { index: number; activeIndex: number }) => void;
    onPostChange?: (event: { index: number }) => void;
    onReactive?: () => void;
    onSwipe?: (index: number, animationOptions: object) => void;
  }

  // Augment Carousel to accept children and proper onPostChange
  export interface CarouselPostChangeEvent {
    activeIndex: number;
    lastActiveIndex: number;
    swipe: unknown;
  }

  export interface CarouselProps {
    children?: React.ReactNode;
    direction?: 'horizontal' | 'vertical';
    fullscreen?: boolean;
    overscrollable?: boolean;
    centered?: boolean;
    itemWidth?: string | number;
    itemHeight?: string | number;
    autoScroll?: boolean;
    autoScrollRatio?: number;
    swipeable?: boolean;
    disabled?: boolean;
    index?: number;
    autoRefresh?: boolean;
    onPostChange?: (event: CarouselPostChangeEvent) => void;
    onRefresh?: () => void;
    onOverscroll?: () => void;
    animationOptions?: object;
  }

  export interface CarouselItemProps {
    children?: React.ReactNode;
    modifier?: string;
  }

  // Augment Switch
  export interface SwitchChangeEvent {
    target: EventTarget | null;
    value: boolean;
  }

  export interface SwitchProps {
    children?: React.ReactNode;
    checked?: boolean;
    disabled?: boolean;
    modifier?: string;
    inputId?: string;
    onChange?: (event: SwitchChangeEvent) => void;
  }

  // Augment Icon
  export interface IconProps {
    children?: React.ReactNode;
    icon?: string;
    size?: number | string;
    rotate?: number;
    fixedWidth?: boolean;
    spin?: boolean;
  }
}
