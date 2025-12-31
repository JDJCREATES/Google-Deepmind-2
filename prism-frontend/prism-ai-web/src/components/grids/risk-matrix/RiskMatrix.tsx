import './RiskMatrix.css';
import AdjustableGrid from '../AdjustableGrid.tsx';
import riskMatrixData from '../../../data/risk-matrix.json'

export interface RiskMatrixProps 
{
  gridWidth: number;
  gridHeight: number;
  gridTitle: string;
  cellData?: any[][];
  renderCell?: (value: any, row: number, col: number) => React.ReactNode;
  onCellClick?: (row: number, col: number) => void;
  cellClassName?: string;
}

const RiskMatrix = 
({
  gridWidth,
  gridHeight,
  gridTitle,
  cellData,
  renderCell,
  onCellClick,
  cellClassName
}: RiskMatrixProps
) => {
  const height = 7;
  const width = 10;
  
  
  
  return (
    <section className="risk-container">
      <AdjustableGrid
        gridWidth={width}
        gridHeight={height}
        gridTitle="Risk & Assurance Matrix"
        cellData={riskMatrixData}
        renderCell={}
        onCellClick={}
        cellClassName="risk-cell"
        />
    </section>
    <aside className="info-link">
      <a src={} />
    </aside>
  )
}

// need to create documentation pages and link to them
// need to create custom tooltip for app wide use and use it here also