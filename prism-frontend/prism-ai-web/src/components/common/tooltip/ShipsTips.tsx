import './ShipsTips.css'

export interface tipsTypes {
  
  tipId: string;
  title: string;
  description: string;
  direction: string;
  
  tipsType?: 'info' | 'warning' | 'demo' | 'feature';
  apiDocLink?: string;
  gifLink?: string: // local path to relevant gif
  gifAlt?: string: //alternaye text for gif/image
}

const ShipsTips = ({ tip }: {tip: tipsTypes}) => {
  
  return (
    <>
      <ons-popover 
        className="ships-tips-container" 
        id={tip.tipId} 
        direction={tip.direction}
        modifier= "tooltip"
        cancelablel
      >
        
        <span className="tip-title">
          {tip.title}
        </span>
        
        <div className="tip-description">
          {tip.description}
          <div className="api-link">
            {tip.apiDocLink}
          </div>
          {tip.gifLink && (
            <div className="gif-section">
              <img
                src={tip.gifLink}
                alt={gifAlt}
              />
            </div>
          )}

        </div>
        
      </ons-popover>
    </>
  )
}

export default ShipsTips;