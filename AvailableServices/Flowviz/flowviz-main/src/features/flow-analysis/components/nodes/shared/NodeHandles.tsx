import { Handle, Position } from 'reactflow';

interface NodeHandlesProps {
  type?: 'default' | 'operator';
}

export function NodeHandles({ type = 'default' }: NodeHandlesProps) {
  if (type === 'operator') {
    return (
      <>
        <Handle 
          type="target" 
          position={Position.Top} 
          style={{ 
            background: 'rgb(245, 158, 11)',
            width: 6,
            height: 6,
            border: '2px solid rgba(0, 0, 0, 0.3)',
            top: -3,
          }} 
        />
        <Handle 
          type="source" 
          position={Position.Bottom} 
          style={{ 
            background: 'rgb(245, 158, 11)',
            width: 6,
            height: 6,
            border: '2px solid rgba(0, 0, 0, 0.3)',
            bottom: -3,
          }} 
        />
      </>
    );
  }

  return (
    <>
      <Handle 
        type="target" 
        position={Position.Top} 
        style={{ 
          background: '#fff',
          width: 6,
          height: 6,
          border: '2px solid rgba(0, 0, 0, 0.3)',
        }} 
      />
      <Handle 
        type="source" 
        position={Position.Bottom} 
        style={{ 
          background: '#fff',
          width: 6,
          height: 6,
          border: '2px solid rgba(0, 0, 0, 0.3)',
        }} 
      />
    </>
  );
}