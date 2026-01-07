import React from 'react'
import './BubbleImage.css'

// renders nothing if the imgSrc isn't provided

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
        width={imgWidth}
        height={imgHeight}
        />
      }
    </>
  )
}

export default BubbleImage;