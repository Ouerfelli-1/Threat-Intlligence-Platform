import React from 'react';
import { getBezierPath, ConnectionLineComponentProps } from 'reactflow';
import { getEdgeParams } from './floatingEdgeHelpers';

const FloatingConnectionLine: React.FC<ConnectionLineComponentProps> = ({
  toX,
  toY,
  fromPosition,
  toPosition,
  fromNode,
}) => {
  if (!fromNode) {
    return null;
  }

  // Create a mock target node at the cursor position
  const targetNode = {
    id: 'connection-target',
    width: 1,
    height: 1,
    position: { x: toX, y: toY },
    internals: {
      positionAbsolute: { x: toX, y: toY },
    },
  };

  const { sx, sy, tx, ty, sourcePos, targetPos } = getEdgeParams(
    fromNode,
    targetNode,
  );

  const [edgePath] = getBezierPath({
    sourceX: sx,
    sourceY: sy,
    sourcePosition: sourcePos || fromPosition,
    targetPosition: targetPos || toPosition,
    targetX: tx || toX,
    targetY: ty || toY,
  });

  return (
    <g>
      <path
        fill="none"
        stroke="rgba(255, 255, 255, 0.5)"
        strokeWidth={1.5}
        strokeDasharray="4 4"
        className="animated"
        d={edgePath}
      />
      <circle
        cx={tx || toX}
        cy={ty || toY}
        fill="#fff"
        r={3}
        stroke="rgba(255, 255, 255, 0.5)"
        strokeWidth={1.5}
      />
    </g>
  );
};

export default FloatingConnectionLine;