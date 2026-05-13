import React from 'react';
import {
  Box,
  Typography,
  IconButton,
  Divider,
  Tooltip
} from '@mui/material';
import { Close as CloseIcon, OpenInNew as OpenInNewIcon } from '@mui/icons-material';
import { ConfidenceChip } from '../../../../../shared/components/Alert';
import { THEME } from '../../constants';
import { NodeDetailsProps } from '../../types';
import {
  isAttackAction,
  isAttackAsset,
  isAttackCondition,
  getMitreLink,
  getTacticName,
  getNodeDisplayName,
  getNodeTypeLabel
} from '../../utils/nodeUtils';

const NodeDetailsPanel: React.FC<NodeDetailsProps> = ({ node, onClose }) => {
  const isActionType = node.type === 'action' || node.type === 'attack-action';
  const displayName = getNodeDisplayName(node);
  const typeLabel = getNodeTypeLabel(node.type);

  const sectionHeaderStyle = {
    color: THEME.text.secondary,
    mb: 1,
    textTransform: 'uppercase' as const,
    fontSize: '0.75rem',
    fontWeight: 600,
    letterSpacing: '0.05em'
  };


  const renderAssetDetails = () => {
    if (!isAttackAsset(node)) return null;

    return (
      <>
        {/* Asset Details */}
        {node.indicator_type && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" sx={sectionHeaderStyle}>
              ASSET DETAILS
            </Typography>
            
            {node.indicator_type && (
              <Box sx={{ mb: 1 }}>
                <Typography variant="caption" sx={{ color: THEME.text.secondary }}>
                  Indicator Type:
                </Typography>
                <Typography variant="body2" sx={{ color: THEME.text.primary, ml: 1 }}>
                  {node.indicator_type.replace('-', ' ').toUpperCase()}
                </Typography>
              </Box>
            )}

            {node.indicator_value && (
              <Box sx={{ mb: 1 }}>
                <Typography variant="caption" sx={{ color: THEME.text.secondary }}>
                  Value:
                </Typography>
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: THEME.text.primary, 
                    ml: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.8rem'
                  }}
                >
                  {node.indicator_value}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </>
    );
  };

  const renderConditionDetails = () => {
    if (!isAttackCondition(node)) return null;
    // Conditions don't need special details - description and context are shown in the main section
    return null;
  };

  return (
    <Box
      sx={{
        position: 'absolute',
        top: THEME.spacing.panel,
        right: THEME.spacing.panel,
        width: 320,
        maxHeight: 'calc(100vh - 100px)',
        overflowY: 'auto',
        overflowX: 'hidden',
        zIndex: 10,
        background: THEME.background.secondary,
        border: THEME.border.default,
        borderRadius: '12px',
        backdropFilter: 'blur(10px)',
        boxShadow: THEME.shadow.panel
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          p: 2,
          borderBottom: THEME.border.default
        }}
      >
        <Box sx={{ flex: 1, pr: 2, minWidth: 0 }}>
          <Typography
            variant="h6"
            sx={{
              background: 'linear-gradient(135deg, #fff 0%, rgba(255, 255, 255, 0.7) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              lineHeight: 1.2,
              mb: 1.5,
              wordBreak: 'break-word',
              overflowWrap: 'break-word',
              hyphens: 'auto',
            }}
          >
            {displayName}
          </Typography>
          
          {/* MITRE ATT&CK Chips - only for action nodes */}
          {isActionType && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {/* Tactic */}
              {(node.tactic_id || node.tactic_name) && (
                <Box
                  component="a"
                  href={node.tactic_id ? `https://attack.mitre.org/tactics/${node.tactic_id}/` : undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '8px 12px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    textDecoration: 'none',
                    color: 'rgba(255, 255, 255, 0.8)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    transition: 'all 0.2s ease-in-out',
                    cursor: 'pointer',
                    width: 'fit-content',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: 'rgba(255, 255, 255, 0.95)'
                    }
                  }}
                >
                  <Typography sx={{ color: 'inherit', fontSize: 'inherit', fontWeight: 'inherit' }}>
                    {node.tactic_id}: {node.tactic_name || getTacticName(node.tactic_id || '')}
                  </Typography>
                  <OpenInNewIcon sx={{ fontSize: '12px', ml: 1, opacity: 0.7 }} />
                </Box>
              )}

              {/* Technique */}
              {node.technique_id && (
                <Box
                  component="a"
                  href={getMitreLink(node.technique_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '8px 12px',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '8px',
                    textDecoration: 'none',
                    color: 'rgba(255, 255, 255, 0.8)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    transition: 'all 0.2s ease-in-out',
                    cursor: 'pointer',
                    width: 'fit-content',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: 'rgba(255, 255, 255, 0.95)'
                    }
                  }}
                >
                  <Typography sx={{ color: 'inherit', fontSize: 'inherit', fontWeight: 'inherit' }}>
                    {node.technique_id}: {node.name}
                  </Typography>
                  <OpenInNewIcon sx={{ fontSize: '12px', ml: 1, opacity: 0.7 }} />
                </Box>
              )}
            </Box>
          )}
        </Box>
        <IconButton
          className="node-details-close-button"
          onClick={onClose}
          sx={{
            color: 'rgba(255, 255, 255, 0.7)',
            minWidth: 'auto',
            minHeight: 'auto',
            padding: '4px',
            '&:hover': {
              color: '#fff',
              backgroundColor: 'transparent'
            }
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ p: 2 }}>
        {/* Description */}
        {'description' in node && node.description && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" sx={sectionHeaderStyle}>
              DESCRIPTION
            </Typography>
            <Typography variant="body2" sx={{ color: THEME.text.primary, lineHeight: 1.5 }}>
              {node.description}
            </Typography>
          </Box>
        )}

        <Divider sx={{ mb: 2, borderColor: 'rgba(255, 255, 255, 0.1)' }} />

        {/* Type-specific details */}
        {renderAssetDetails()}
        {renderConditionDetails()}

        {/* Source Evidence */}
        {'source_excerpt' in node && node.source_excerpt && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" sx={sectionHeaderStyle}>
              SOURCE TEXT
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: THEME.text.primary,
                fontSize: '0.85rem',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                padding: 1.5,
                borderRadius: '6px',
                border: THEME.border.default,
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontStyle: 'italic'
              }}
            >
              "{node.source_excerpt}"
            </Typography>
          </Box>
        )}

        {/* Confidence Level */}
        {'confidence' in node && node.confidence && (
          <Box sx={{ mb: 2 }}>
            <Tooltip
              title="Confidence in extraction accuracy based on source text clarity"
              placement="top"
              arrow
              slotProps={{
                tooltip: {
                  sx: {
                    backgroundColor: THEME.background.tertiary,
                    color: THEME.text.primary,
                    fontSize: '0.75rem',
                    fontWeight: 500,
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: THEME.border.default,
                    backdropFilter: 'blur(10px)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
                    maxWidth: '240px'
                  }
                },
                arrow: {
                  sx: {
                    color: THEME.background.tertiary,
                    '&::before': {
                      border: THEME.border.default
                    }
                  }
                }
              }}
            >
              <ConfidenceChip confidence={node.confidence as 'low' | 'medium' | 'high'} />
            </Tooltip>
          </Box>
        )}

      </Box>
    </Box>
  );
};

export default NodeDetailsPanel;