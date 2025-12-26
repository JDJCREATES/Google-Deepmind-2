import { useFileSystem } from '../../store/fileSystem';
import FileTreeNode from './FileTreeNode';

export default function FileTree() {
  const { files } = useFileSystem();

  if (files.length === 0) return null;

  return (
    <div className="file-tree-container">
      {files.map(node => (
        <FileTreeNode key={node.id} node={node} level={0} />
      ))}
    </div>
  );
}
