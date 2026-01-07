import React from 'react'
import './BubbleImage.css'

// renders nothing if the imgSrc isn't provided for now

export interface BubImgType = {
  imgSrc: string;
  imgAlt: string;
  imgWidth: number;
  imgHeight: number;
}

const BubbleImage =({props}: {props: BubImgTypes} ) => {
  
  return (
    <>
      {imgSrc && 
      <img
        src={props.imgSrc} 
        alt={props.imgAlt} 
        width={props.imgWidth}
        height={props.imgHeight}
        className="bubble-image"
        />
      }
    </>
  )
}

export default BubbleImage;