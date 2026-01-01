/**
 * Timeline Controls Component
 * 
 * Navigation, filters, and search controls for the timeline
 */

import { useState } from 'react';
import { FiChevronLeft, FiChevronRight, FiSearch, FiFilter } from 'react-icons/fi';
import { FilterType } from '../../types/timeline';
import './TimelineControls.css';

interface TimelineControlsProps {
  onScrollLeft?: () => void;
  onScrollRight?: () => void;
  onSearch?: (query: string) => void;
  onFilterChange?: (filter: FilterType) => void;
  currentFilter?: FilterType;
  canScrollLeft?: boolean;
  canScrollRight?: boolean;
}

export function TimelineControls({
  onScrollLeft,
  onScrollRight,
  onSearch,
  onFilterChange,
  currentFilter = 'all',
  canScrollLeft = false,
  canScrollRight = false
}: TimelineControlsProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch?.(searchQuery);
  };

  const filters: { value: FilterType; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'features', label: 'Features' },
    { value: 'fixes', label: 'Fixes' },
    { value: 'refactors', label: 'Refactors' },
    { value: 'deploys', label: 'Deploys' }
  ];

  return (
    <div className="timeline-controls">
      {/* Scroll Controls */}
      <div className="timeline-scroll-controls">
        <button 
          className="scroll-btn"
          onClick={onScrollLeft}
          disabled={!canScrollLeft}
          title="Scroll Left"
        >
          <FiChevronLeft size={20} />
        </button>
        <button 
          className="scroll-btn"
          onClick={onScrollRight}
          disabled={!canScrollRight}
          title="Scroll Right"
        >
          <FiChevronRight size={20} />
        </button>
      </div>

      {/* Search */}
      <form className="timeline-search" onSubmit={handleSearch}>
        <FiSearch size={14} className="search-icon" />
        <input
          type="text"
          className="search-input"
          placeholder="Search timeline..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </form>

      {/* Filters */}
      <div className="timeline-filters">
        <button 
          className="filter-toggle-btn"
          onClick={() => setShowFilters(!showFilters)}
          title="Filters"
        >
          <FiFilter size={16} />
          <span className="filter-label">{currentFilter}</span>
        </button>
        
        {showFilters && (
          <div className="filter-dropdown">
            {filters.map(filter => (
              <button
                key={filter.value}
                className={`filter-option ${currentFilter === filter.value ? 'active' : ''}`}
                onClick={() => {
                  onFilterChange?.(filter.value);
                  setShowFilters(false);
                }}
              >
                {filter.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
