import './PlanReviewActions.css';

interface PlanReviewActionsProps {
  planSummary: string;
  onAccept: () => void;
  onReject: () => void;
  isLoading?: boolean;
}

/**
 * Human-in-the-Loop Plan Review Actions
 * 
 * Shows Accept/Reject buttons when the agent is waiting for user confirmation
 * to proceed with the implementation plan.
 */
export function PlanReviewActions({ 
  planSummary, 
  onAccept, 
  onReject,
  isLoading = false 
}: PlanReviewActionsProps) {
  return (
    <div className="plan-review-container">
      <div className="plan-review-header">
        <span className="plan-review-icon">📋</span>
        <span className="plan-review-title">Plan Ready for Review</span>
      </div>
      
      {planSummary && (
        <div className="plan-review-summary">
          {planSummary}
        </div>
      )}
      
      <div className="plan-review-actions">
        <button 
          className="plan-review-btn accept"
          onClick={onAccept}
          disabled={isLoading}
        >
          <span className="btn-icon">✓</span>
          <span className="btn-text">Accept & Build</span>
        </button>
        
        <button 
          className="plan-review-btn reject"
          onClick={onReject}
          disabled={isLoading}
        >
          <span className="btn-icon">✗</span>
          <span className="btn-text">Reject / Edit</span>
        </button>
      </div>
      
      <div className="plan-review-hint">
        Or type your feedback below to refine the plan
      </div>
    </div>
  );
}
