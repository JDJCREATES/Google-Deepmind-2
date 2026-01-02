

export interface tipsTypes {
  
  tipId: string;
  title: string;
  description: string;
  direction: string;
  
  apiDocLink?: string;
  
}

const ShipsTips = ({tipId, title, description, direction, apiDocLink}: tipsTypes) => {
  
  return (
    <>
      <ons-popover className="ships-tips-container" id={tipId} direction={direction}>
        
        <span className="tip-title">
          {title}
        </span>
        
        <div className="tip-description">
          {description}
          <div className="api-link">
            {apiDocLink}
          </div>
        </div>
        
      </ons-popover>
    </>
  )
}

export default ShipsTips;