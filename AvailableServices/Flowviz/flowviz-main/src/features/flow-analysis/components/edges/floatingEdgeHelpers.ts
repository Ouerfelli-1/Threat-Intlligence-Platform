import { Node, Position } from 'reactflow';

// Helper to get the position of the handle based on node position and type
function getHandlePosition(
  nodeA: Node,
  nodeB: Node,
  sourceType?: string,
  targetType?: string
): { source: Position; target: Position } {
  const centerA = {
    x: nodeA.position.x + (nodeA.width || 200) / 2,
    y: nodeA.position.y + (nodeA.height || 120) / 2,
  };

  const centerB = {
    x: nodeB.position.x + (nodeB.width || 200) / 2,
    y: nodeB.position.y + (nodeB.height || 120) / 2,
  };

  // For dagre layout, always use vertical connections (top/bottom)
  // This ensures proper alignment with the hierarchical layout
  if (centerA.y > centerB.y) {
    return { source: Position.Top, target: Position.Bottom };
  } else {
    return { source: Position.Bottom, target: Position.Top };
  }
}

// Get the actual coordinates for the edge connection points
export function getEdgeParams(sourceNode: any, targetNode: any) {
  // Handle internal node structure from useStore - fallback to positionAbsolute if position is not available
  const sourcePos = sourceNode.position || sourceNode.positionAbsolute;
  const targetPos = targetNode.position || targetNode.positionAbsolute;
  
  const sourceNodeData = {
    position: sourcePos,
    width: sourceNode.width || 200,
    height: sourceNode.height || 120,
  };
  
  const targetNodeData = {
    position: targetPos,
    width: targetNode.width || 200,
    height: targetNode.height || 120,
  };

  const { source: sourceHandlePos, target: targetHandlePos } = getHandlePosition(
    sourceNodeData as Node,
    targetNodeData as Node,
    sourceNode.type,
    targetNode.type
  );

  const sourceWidth = sourceNode.width || 200;
  const sourceHeight = sourceNode.height || 120;
  const targetWidth = targetNode.width || 200;
  const targetHeight = targetNode.height || 120;

  const sourceX = sourcePos.x;
  const sourceY = sourcePos.y;
  const targetX = targetPos.x;
  const targetY = targetPos.y;

  // Calculate handle positions based on the determined positions
  let sx = sourceX;
  let sy = sourceY;
  let tx = targetX;
  let ty = targetY;

  switch (sourceHandlePos) {
    case Position.Top:
      sx = sourceX + sourceWidth / 2;
      sy = sourceY;
      break;
    case Position.Bottom:
      sx = sourceX + sourceWidth / 2;
      sy = sourceY + sourceHeight;
      break;
    default:
      // Fallback to bottom for any unexpected case
      sx = sourceX + sourceWidth / 2;
      sy = sourceY + sourceHeight;
      break;
  }

  switch (targetHandlePos) {
    case Position.Top:
      tx = targetX + targetWidth / 2;
      ty = targetY;
      break;
    case Position.Bottom:
      tx = targetX + targetWidth / 2;
      ty = targetY + targetHeight;
      break;
    default:
      // Fallback to top for any unexpected case
      tx = targetX + targetWidth / 2;
      ty = targetY;
      break;
  }

  return { sx, sy, tx, ty, sourcePos: sourceHandlePos, targetPos: targetHandlePos };
}