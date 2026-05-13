import React, { useState, useEffect } from 'react';
import {
  Box,
  IconButton,
  Typography,
  LinearProgress,
  Paper,
  Tooltip,
  Collapse
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  Replay,
  Close,
  ExpandLess,
  ExpandMore
} from '@mui/icons-material';
import { StoryModeState, StoryModeControls as StoryModeControlsType, StoryStep } from '../hooks/useStoryMode';

interface StoryModeControlsProps {
  storyState: StoryModeState;
  controls: StoryModeControlsType;
  currentStepData: StoryStep | null;
  onClose: () => void;
}

const StoryModeControls: React.FC<StoryModeControlsProps> = ({
  storyState,
  controls,
  currentStepData,
  onClose
}) => {
  const { isPlaying, currentStep, steps, progress } = storyState;
  const { playStory, pauseStory, nextStep, prevStep, resetStory } = controls;
  
  // Smart visibility states
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasUserInteracted, setHasUserInteracted] = useState(false);

  // Auto-expand when story is playing
  useEffect(() => {
    if (isPlaying) {
      setIsExpanded(true);
    }
  }, [isPlaying]);

  // Auto-collapse after inactivity (unless playing)
  useEffect(() => {
    if (!isPlaying && hasUserInteracted && isExpanded) {
      const timer = setTimeout(() => {
        setIsExpanded(false);
      }, 3000); // Collapse after 3 seconds of inactivity
      
      return () => clearTimeout(timer);
    }
  }, [isPlaying, hasUserInteracted, isExpanded, currentStep]);

  // Track user interactions
  const handleUserInteraction = (action: () => void) => {
    setHasUserInteracted(true);
    setIsExpanded(true);
    action();
  };

  if (steps.length === 0) return null;

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'absolute',
        top: 24,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        background: 'rgba(13, 17, 23, 0.85)',
        backdropFilter: 'blur(24px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '12px 24px',
        minWidth: isExpanded ? '500px' : '320px',
        maxWidth: '600px',
        boxShadow: '0 8px 25px -5px rgba(0, 0, 0, 0.3), 0 4px 14px -3px rgba(0, 0, 0, 0.2)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
    >
      {/* Compact Title Bar */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center',
        gap: 2,
        mb: isExpanded ? 2 : 0
      }}>
        {/* Story Mode Indicator & Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: isPlaying ? '#10b981' : '#3b82f6',
              boxShadow: isPlaying 
                ? '0 0 8px rgba(16, 185, 129, 0.6)' 
                : '0 0 8px rgba(59, 130, 246, 0.6)',
              animation: isPlaying ? 'pulse 2s infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 }
              }
            }}
          />
          <Typography
            variant="body2"
            sx={{
              color: '#fff',
              fontWeight: 500,
              fontSize: '0.9rem',
            }}
          >
            {currentStepData?.title || `Step ${currentStep + 1} of ${steps.length}`}
          </Typography>
          
          {/* Compact Progress Bar */}
          <Box sx={{ flex: 1, mx: 2, maxWidth: 120 }}>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{
                height: 3,
                borderRadius: 2,
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: '#3b82f6',
                  borderRadius: 2,
                }
              }}
            />
          </Box>
        </Box>

        {/* Compact Controls */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title="Previous Step" placement="bottom">
            <span>
              <IconButton
                onClick={() => handleUserInteraction(prevStep)}
                disabled={currentStep <= 0}
                size="small"
                sx={{
                  color: 'rgba(255, 255, 255, 0.6)',
                  width: 32,
                  height: 32,
                  '&:hover': { 
                    color: 'rgba(255, 255, 255, 0.9)',
                    backgroundColor: 'rgba(255, 255, 255, 0.08)'
                  },
                  '&.Mui-disabled': {
                    color: 'rgba(255, 255, 255, 0.2)'
                  }
                }}
              >
                <SkipPrevious fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title={isPlaying ? "Pause Story" : "Play Story"} placement="bottom">
            <IconButton
              onClick={() => handleUserInteraction(isPlaying ? pauseStory : playStory)}
              sx={{
                backgroundColor: '#3b82f6',
                color: '#fff',
                width: 36,
                height: 36,
                mx: 0.5,
                '&:hover': { 
                  backgroundColor: '#2563eb',
                  transform: 'scale(1.05)'
                },
                transition: 'all 0.15s ease',
                boxShadow: '0 2px 8px 0 rgba(59, 130, 246, 0.4)'
              }}
            >
              {isPlaying ? <Pause fontSize="small" /> : <PlayArrow fontSize="small" />}
            </IconButton>
          </Tooltip>

          <Tooltip title="Next Step" placement="bottom">
            <span>
              <IconButton
                onClick={() => handleUserInteraction(nextStep)}
                disabled={currentStep >= steps.length - 1}
                size="small"
                sx={{
                  color: 'rgba(255, 255, 255, 0.6)',
                  width: 32,
                  height: 32,
                  '&:hover': { 
                    color: 'rgba(255, 255, 255, 0.9)',
                    backgroundColor: 'rgba(255, 255, 255, 0.08)'
                  },
                  '&.Mui-disabled': {
                    color: 'rgba(255, 255, 255, 0.2)'
                  }
                }}
              >
                <SkipNext fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          {/* Expand/Collapse Toggle */}
          <Tooltip title={isExpanded ? "Collapse" : "Expand"} placement="bottom">
            <IconButton 
              onClick={() => setIsExpanded(!isExpanded)}
              size="small"
              sx={{ 
                color: 'rgba(255, 255, 255, 0.5)',
                width: 32,
                height: 32,
                ml: 0.5,
                '&:hover': { 
                  color: 'rgba(255, 255, 255, 0.8)',
                  backgroundColor: 'rgba(255, 255, 255, 0.05)'
                }
              }}
            >
              {isExpanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Close Story Mode" placement="bottom">
            <IconButton 
              onClick={onClose}
              size="small"
              sx={{ 
                color: 'rgba(255, 255, 255, 0.5)',
                width: 32,
                height: 32,
                '&:hover': { 
                  color: 'rgba(255, 255, 255, 0.8)',
                  backgroundColor: 'rgba(255, 255, 255, 0.05)'
                }
              }}
            >
              <Close fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Expanded Details */}
      <Collapse in={isExpanded} timeout={300}>
        <Box>
          {/* Step Description */}
          {currentStepData?.description && (
            <Typography
              variant="body2"
              sx={{
                color: 'rgba(255, 255, 255, 0.7)',
                fontSize: '0.85rem',
                mb: 2,
                textAlign: 'center'
              }}
            >
              {currentStepData.description}
            </Typography>
          )}

          {/* Secondary Controls */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center',
            gap: 2,
            mb: 2
          }}>
            <Tooltip title="Reset Story" placement="bottom">
              <IconButton
                onClick={() => handleUserInteraction(resetStory)}
                size="small"
                sx={{
                  color: 'rgba(255, 255, 255, 0.4)',
                  width: 32,
                  height: 32,
                  '&:hover': { 
                    color: 'rgba(255, 255, 255, 0.7)',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)'
                  }
                }}
              >
                <Replay fontSize="small" />
              </IconButton>
            </Tooltip>

            <Typography
              variant="caption"
              sx={{
                color: 'rgba(255, 255, 255, 0.5)',
                fontSize: '0.75rem',
                mx: 2
              }}
            >
              {currentStep + 1} of {steps.length} steps
            </Typography>
          </Box>

          {/* Step Indicators */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'center', 
            gap: 0.75,
            flexWrap: 'wrap'
          }}>
            {steps.map((_, index) => (
              <Tooltip key={index} title={`Go to step ${index + 1}`} placement="bottom">
                <Box
                  onClick={() => handleUserInteraction(() => controls.goToStep(index))}
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: index === currentStep 
                      ? '#3b82f6' 
                      : 'rgba(255, 255, 255, 0.25)',
                    cursor: 'pointer',
                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      backgroundColor: index === currentStep 
                        ? '#2563eb' 
                        : 'rgba(255, 255, 255, 0.4)',
                      transform: 'scale(1.4)'
                    }
                  }}
                />
              </Tooltip>
            ))}
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
};

export default StoryModeControls;