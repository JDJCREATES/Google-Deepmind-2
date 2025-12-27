import './MatrixGrid.css'

export interface matrixProps = {
  gridWidth: number,
  gridHeight: number,
  gridTitle: string,
  
  defaultCellColor: string,
  currentCellColor: string,
  
  
}


const MatrixGrid = ({props: matrixProps }) => {
  const cellCount = props.gridWidth x props.gridHeight;
  
  return (
    <>
      <section className="grid-container">
        <div className="grid-title">
          {props.gridTitle}
        </div>
        {}
      </section>
    </>
  )
}