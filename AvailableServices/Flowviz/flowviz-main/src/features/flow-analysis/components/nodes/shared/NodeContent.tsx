import { Typography, Link, Tooltip } from '@mui/material';
import { getTextStyle, getMitreLink, hasDescription, hasName, isAttackAction } from './nodeUtils';

interface NodeContentProps {
  data: any;
  showTechniqueLink?: boolean;
  showCommandLine?: boolean;
  showTacticId?: boolean;
}

export function NodeContent({ 
  data, 
  showTechniqueLink = false, 
  showCommandLine = false,
  showTacticId = false
}: NodeContentProps) {
  const displayText = hasName(data) ? data.name : data.type;
  const { text, style } = getTextStyle(displayText);

  return (
    <>
      {/* Node Name/Title */}
      <Tooltip 
        title={displayText}
        placement="top"
        disableInteractive
      >
        <Typography variant="h6" component="div" sx={{ 
          color: '#fff', 
          mb: 1, 
          fontSize: '0.95rem', 
          fontWeight: 600,
          lineHeight: 1.3,
          maxWidth: '220px',
          ...style
        }}>
          {text}
          {showTechniqueLink && isAttackAction(data) && data.technique_id && data.technique_id !== data.name && (
            <Link
              href={getMitreLink(data.technique_id)}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                ml: 1,
                color: 'rgba(255, 255, 255, 0.6)',
                fontSize: '0.8rem',
                textDecoration: 'none',
                '&:hover': {
                  color: '#fff',
                  textDecoration: 'underline'
                }
              }}
            >
              ({data.technique_id})
            </Link>
          )}
        </Typography>
      </Tooltip>

      {/* Description */}
      {hasDescription(data) && (
        <Typography
          variant="body2"
          sx={{
            color: 'rgba(255, 255, 255, 0.7)',
            fontSize: '0.8rem',
            lineHeight: 1.4,
            mb: 1,
            wordBreak: 'break-word'
          }}
        >
          {data.description}
        </Typography>
      )}

      {/* Command line display for tool/malware nodes */}
      {showCommandLine && (data.type === 'tool' || data.type === 'malware') && 
       data.command_line && data.command_line.trim() && (
        <Typography
          variant="body2"
          sx={{
            color: 'rgba(255, 255, 255, 0.8)',
            fontSize: '0.75rem',
            fontFamily: 'Monaco, Consolas, "Courier New", monospace',
            lineHeight: 1.3,
            mb: 1,
            backgroundColor: 'rgba(0, 0, 0, 0.3)',
            padding: '4px 6px',
            borderRadius: '3px',
            wordBreak: 'break-all',
            border: '1px solid rgba(255, 255, 255, 0.1)'
          }}
        >
          {data.command_line}
        </Typography>
      )}

      {/* Tactic ID for attack actions */}
      {showTacticId && isAttackAction(data) && data.tactic_id && (
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            color: 'rgba(255, 255, 255, 0.5)',
            fontSize: '0.7rem',
            fontWeight: 500
          }}
        >
          {data.tactic_id}
        </Typography>
      )}
    </>
  );
}