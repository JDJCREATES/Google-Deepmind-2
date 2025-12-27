import './AdjustableGrid.css'

export interface AdjustableGridProps {
  gridWidth: number;
  gridHeight: number;
  cellData?: any[][];
  renderCell?: (value: any, row: number, col: number) => React.ReactNode;
  onCellClick?: (row: number, col: number) => void;
  cellClassName?: string;
}

const AdjustableGrid = ({
  gridWidth,
  gridHeight,
  cellData,
  renderCell,
  onCellClick,
  cellClassName = ""
}: AdjustableGridProps) => {
  const cellCount = gridWidth * gridHeight;

  // Generate cells
  const cells = [];
  for (let i = 0; i < cellCount; i++) {
    const row = Math.floor(i / gridWidth);
    const col = i % gridWidth;
    
    // Get cell value if cellData is provided
    const cellValue = cellData?.[row]?.[col];
    
    cells.push(
      <div
        key={i}
        className={`grid-cell ${cellClassName}`}
        onClick={() => onCellClick?.(row, col)}
      >
        {renderCell ? renderCell(cellValue, row, col) : cellValue}
      </div>
    );
  }

  return (
    <div
      className="adjustable-grid"
      style={{
        gridTemplateColumns: `repeat(${gridWidth}, 1fr)`,
        gridTemplateRows: `repeat(${gridHeight}, 1fr)`
      }}
    >
      {cells}
    </div>
  );
};

export default AdjustableGrid;