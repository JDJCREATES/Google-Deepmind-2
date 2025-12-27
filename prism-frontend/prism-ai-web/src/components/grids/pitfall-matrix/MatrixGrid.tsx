import AdjustableGrid from './AdjustableGrid';

export interface MatrixGridProps {
  gridWidth: number;
  gridHeight: number;
  gridTitle: string;
  cellData?: any[][];
  renderCell?: (value: any, row: number, col: number) => React.ReactNode;
  onCellClick?: (row: number, col: number) => void;
  cellClassName?: string;
}

const MatrixGrid = ({
  gridWidth,
  gridHeight,
  gridTitle,
  cellData,
  renderCell,
  onCellClick,
  cellClassName
}: MatrixGridProps) => {
  return (
    <>
      <section className="grid-container">
        <div className="grid-title">{gridTitle}</div>
        <AdjustableGrid
          gridWidth={gridWidth}
          gridHeight={gridHeight}
          cellData={cellData}
          renderCell={renderCell}
          onCellClick={onCellClick}
          cellClassName={cellClassName}
        />
      </section>
    </>
  );
};

export default MatrixGrid;