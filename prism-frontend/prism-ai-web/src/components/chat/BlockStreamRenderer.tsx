import React from 'react';
import type { StreamBlock } from '../agent-dashboard/types';
import Editor from '@monaco-editor/react';
import { formatMarkdown } from './utils/simpleMarkdown';

interface BlockProps {
    block: StreamBlock;
}

export const BlockRenderer: React.FC<BlockProps> = ({ block }) => {
    switch (block.type) {
        case 'thinking':
            return (
                <div className="block-thinking" style={{ 
                    borderLeft: '2px solid #555', 
                    paddingLeft: '12px', 
                    margin: '8px 0', 
                    color: '#999',
                    fontSize: '0.9em'
                }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#888' }}>
                         {block.isComplete ? '✓ ' : '⚡ '}{block.title || 'Thinking...'}
                    </div>
                    {(block.content || !block.isComplete) && (
                        <div style={{ opacity: 0.9, lineHeight: '1.5' }}>
                            {formatMarkdown(block.content)}
                        </div>
                    )}
                </div>
            );
        case 'command':
             return (
                <div className="block-command" style={{
                    backgroundColor: '#1E1E1E',
                    color: '#4ADE80',
                    padding: '10px',
                    borderRadius: '6px',
                    fontFamily: 'monospace',
                    fontSize: '0.85em',
                    margin: '8px 0',
                    border: '1px solid #333'
                }}>
                    <div style={{ color: '#6B7280', marginBottom: '6px', userSelect: 'none' }}>
                        $ {block.title || 'Command'}
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>
                        {block.content}
                    </div>
                </div>
             );
        case 'code':
             // Detect language from title or content? default to typescript
             return (
                 <div className="block-code" style={{ 
                      margin: '12px 0', 
                      borderRadius: '6px', 
                      overflow: 'hidden',
                      border: '1px solid #333'
                 }}>
                     <Editor 
                        height="200px" // Dynamic height would be better but requires more logic
                        defaultLanguage="typescript"
                        value={block.content}
                        theme="vs-dark"
                        options={{
                            readOnly: true,
                            minimap: { enabled: false },
                            scrollBeyondLastLine: false,
                            fontSize: 12,
                            lineNumbers: 'on',
                            renderLineHighlight: 'none'
                        }}
                     />
                 </div>
             );
        case 'plan':
            return (
                <div className="block-plan" style={{
                    backgroundColor: 'rgba(30, 58, 138, 0.3)',
                    border: '1px solid rgba(59, 130, 246, 0.4)',
                    borderRadius: '8px',
                    padding: '16px',
                    margin: '12px 0'
                }}>
                    <h3 style={{ color: '#60A5FA', fontWeight: 'bold', marginBottom: '12px', fontSize: '1.1em' }}>
                        {block.title || 'Implementation Plan'}
                    </h3>
                    <div style={{ lineHeight: '1.5', color: '#D1D5DB' }}>
                        {formatMarkdown(block.content)}
                    </div>
                </div>
            )
        case 'preflight':
            return (
                <div className="block-preflight" style={{
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.4)',
                    borderRadius: '8px',
                    padding: '12px',
                    margin: '8px 0'
                }}>
                    <div style={{ color: '#10B981', fontWeight: 'bold', marginBottom: '8px' }}>
                        {block.title || '🔧 Preflight Checks'}
                    </div>
                    <div style={{ lineHeight: '1.5', color: '#D1D5DB' }}>
                        {formatMarkdown(block.content)}
                    </div>
                </div>
            )
        case 'error':
             return (
                <div className="block-error" style={{
                    backgroundColor: 'rgba(220, 38, 38, 0.1)',
                    border: '1px solid rgba(220, 38, 38, 0.4)',
                    color: '#EF4444',
                    padding: '12px',
                    borderRadius: '6px',
                    margin: '8px 0'
                }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>
                        {block.title || 'Error'}
                    </div>
                    <div style={{ lineHeight: '1.5' }}>
                        {formatMarkdown(block.content)}
                    </div>
                </div>
             );
        case 'cmd_output':
            return (
                <div className="block-cmd-output" style={{
                    backgroundColor: '#1A1A1A',
                    border: '1px solid #2A2A2A',
                    borderRadius: '6px',
                    padding: '12px',
                    margin: '8px 0',
                    fontFamily: 'monospace',
                    fontSize: '0.85em'
                }}>
                    {block.title && (
                        <div style={{ color: '#6B7280', marginBottom: '8px', fontSize: '0.9em' }}>
                            {block.title}
                        </div>
                    )}
                    <div style={{ 
                        whiteSpace: 'pre-wrap', 
                        color: '#D1D5DB',
                        lineHeight: '1.5',
                        overflowX: 'auto'
                    }}>
                        {formatMarkdown(block.content)}
                    </div>
                </div>
            );
        case 'tool_use':
            return (
                <div className="block-tool-use" style={{
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                    borderRadius: '6px',
                    padding: '10px 12px',
                    margin: '6px 0',
                    fontSize: '0.9em'
                }}>
                    <div style={{ color: '#60A5FA', fontWeight: '500' }}>
                        {block.title || 'Tool'}
                    </div>
                    {block.content && (
                        <div style={{ color: '#9CA3AF', marginTop: '4px' }}>
                            {block.content}
                        </div>
                    )}
                </div>
            );
        case 'text':
        default:
            return (
                <div className="block-text" style={{ 
                    whiteSpace: 'pre-wrap', 
                    margin: '8px 0',
                    lineHeight: '1.5'
                }}>
                    {block.content}
                </div>
            );
    }
}
