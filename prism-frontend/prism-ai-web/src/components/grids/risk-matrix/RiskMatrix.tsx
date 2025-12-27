import './RiskMatrix.css';

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
  
  
  return (
    
  )
}