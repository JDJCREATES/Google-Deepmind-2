import './FeatureTimeline.css'
import featureTypes from '../featureTypes.ts'
import { useState, useEffect, useMemo } from 'react'

const FeatureTimeline = ({props}: {props: featureTypes } ) => {
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  
  const toggleNode = (nodeId: ) => {
  const newExpanded = new Set(expandedNodes);
  if (newExpanded.has(nodeId)) {
    newExpanded.delete(nodeId);
  } else {
    newExpanded.add(nodeId);
  }
  setExpandedNodes(newExpanded);
}
  
  return (
    <section className="feature-timeline">
      <div className="timeline-header">
        
      </div>
      
      <ons-carousel className="timeline-container">
        
      </ons-carousel>
    </section>
  )
}

export default FeatureTimeline;