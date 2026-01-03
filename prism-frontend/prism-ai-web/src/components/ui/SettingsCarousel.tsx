import React, { useState, useCallback } from 'react';
import './SettingsCarousel.css';

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

export interface SettingsCarouselProps {
  /** Array of slide content or single slide */
  children: React.ReactNode;
  /** Optional initial slide index */
  initialIndex?: number;
  /** Called when slide changes */
  onSlideChange?: (index: number) => void;
  /** Show pagination dots */
  showPagination?: boolean;
}

export interface CarouselSlideProps {
  children: React.ReactNode;
  className?: string;
}

// ─────────────────────────────────────────────────────────────
// CarouselSlide - Individual slide wrapper
// ─────────────────────────────────────────────────────────────

export const CarouselSlide: React.FC<CarouselSlideProps> = ({ children, className = '' }) => {
  return (
    <div className={`carousel-slide ${className}`}>
      {children}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// SettingsCarousel - Main carousel component
// ─────────────────────────────────────────────────────────────

export const SettingsCarousel: React.FC<SettingsCarouselProps> = ({
  children,
  initialIndex = 0,
  onSlideChange,
  showPagination = true,
}) => {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const slideCount = React.Children.count(children);

  const goToSlide = useCallback((index: number) => {
    if (index >= 0 && index < slideCount) {
      setCurrentIndex(index);
      onSlideChange?.(index);
    }
  }, [slideCount, onSlideChange]);

  const goToPrev = useCallback(() => {
    if (currentIndex > 0) {
      goToSlide(currentIndex - 1);
    }
  }, [currentIndex, goToSlide]);

  const goToNext = useCallback(() => {
    if (currentIndex < slideCount - 1) {
      goToSlide(currentIndex + 1);
    }
  }, [currentIndex, slideCount, goToSlide]);

  return (
    <div className="settings-carousel">
      <div className="carousel-track-container">
        <div 
          className="carousel-track"
          style={{ transform: `translateX(-${currentIndex * 100}%)` }}
        >
          {React.Children.map(children, (child, index) => (
            <div 
              key={index} 
              className="carousel-slide-wrapper"
              aria-hidden={index !== currentIndex}
            >
              {child}
            </div>
          ))}
        </div>
      </div>

      {showPagination && slideCount > 1 && (
        <div className="carousel-navigation">
          {/* Previous Arrow */}
          <button
            type="button"
            className="carousel-arrow carousel-arrow-prev"
            onClick={goToPrev}
            disabled={currentIndex === 0}
            aria-label="Previous page"
          >
            ←
          </button>

          {/* Pagination Dots */}
          <div className="carousel-pagination">
            {Array.from({ length: slideCount }).map((_, index) => (
              <button
                key={index}
                type="button"
                className={`carousel-dot ${index === currentIndex ? 'active' : ''}`}
                onClick={() => goToSlide(index)}
                aria-label={`Go to slide ${index + 1}`}
                aria-current={index === currentIndex ? 'true' : 'false'}
              />
            ))}
          </div>

          {/* Next Arrow */}
          <button
            type="button"
            className="carousel-arrow carousel-arrow-next"
            onClick={goToNext}
            disabled={currentIndex === slideCount - 1}
            aria-label="Next page"
          >
            →
          </button>
        </div>
      )}
    </div>
  );
};

export default SettingsCarousel;
