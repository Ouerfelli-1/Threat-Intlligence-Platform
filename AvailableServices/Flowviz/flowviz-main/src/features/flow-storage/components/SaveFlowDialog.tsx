import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  LinearProgress
} from '@mui/material';
import { FlowAlert } from '../../../shared/components/Alert';
import { 
  EnhancedDialog,
  EnhancedDialogContent,
  EnhancedDialogActions,
  PrimaryButton,
  SecondaryButton 
} from '../../../shared/components/EnhancedDialog';
import { 
  EnhancedTextField
} from '../../../shared/components/EnhancedForm';
import { Node, Edge, Viewport } from 'reactflow';
import { SavedFlow } from '../types/SavedFlow';
import { LocalStorageService, StorageError } from '../services';

interface SaveFlowDialogProps {
  open: boolean;
  onClose: () => void;
  nodes: Node[];
  edges: Edge[];
  sourceUrl?: string;
  sourceText?: string;
  inputMode: 'url' | 'text';
  viewport?: Viewport;
  onSave: (flow: SavedFlow) => void;
}

const SaveFlowDialog: React.FC<SaveFlowDialogProps> = ({
  open,
  onClose,
  nodes,
  edges,
  sourceUrl,
  sourceText,
  inputMode,
  viewport,
  onSave
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const storageService = new LocalStorageService();

  // Auto-generate title based on source when dialog opens
  useEffect(() => {
    if (open && !title) {
      generateTitle();
    }
  }, [open, sourceUrl, inputMode]);

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      setTitle('');
      setDescription('');
      setError(null);
      setSaving(false);
    }
  }, [open]);

  const generateTitle = () => {
    const date = new Date().toLocaleDateString();
    
    if (inputMode === 'url' && sourceUrl) {
      try {
        const url = new URL(sourceUrl);
        const domain = url.hostname.replace('www.', '');
        setTitle(`Analysis from ${domain} - ${date}`);
      } catch {
        setTitle(`URL Analysis - ${date}`);
      }
    } else {
      setTitle(`Text Analysis - ${date}`);
    }
  };

  const extractTechniquesAndTactics = () => {
    const techniques: string[] = [];
    const tactics: string[] = [];
    
    nodes.forEach(node => {
      if (node.data.techniques) {
        techniques.push(...node.data.techniques);
      }
      if (node.data.tactics) {
        tactics.push(...node.data.tactics);
      }
    });
    
    return {
      techniques: [...new Set(techniques)],
      tactics: [...new Set(tactics)]
    };
  };

  const handleSave = async () => {
    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const { techniques, tactics } = extractTechniquesAndTactics();
      
      const flow: SavedFlow = {
        id: crypto.randomUUID(),
        title: title.trim(),
        sourceUrl,
        sourceText,
        inputMode,
        nodes,
        edges,
        metadata: {
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          version: '1.0.0',
          description: description.trim() || undefined,
          tags: [],
          nodeCount: nodes.length,
          edgeCount: edges.length,
        },
        visualization: {
          viewport,
          storyMode: { enabled: false }
        },
        analysis: {
          extractedTechniques: techniques,
          extractedTactics: tactics
        }
      };

      await storageService.saveFlow(flow);
      onSave(flow);
      onClose();
    } catch (err) {
      if (err instanceof StorageError) {
        setError(err.message);
      } else {
        setError('Failed to save flow. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <EnhancedDialog 
      open={open} 
      onClose={onClose}
      title="Save Analysis"
      maxWidth="sm"
      fullWidth
      dialogMaxWidth="600px"
    >
      <EnhancedDialogContent sx={{ 
        overflow: 'visible',
        '&::-webkit-scrollbar': { display: 'none' },
        scrollbarWidth: 'none',
      }}>
        {error && (
          <FlowAlert
            status="error"
            sx={{ mb: 2 }}
          >
            {error}
          </FlowAlert>
        )}
        
        <Box sx={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 2.5, 
          mt: 1,
          width: '100%',
          maxWidth: '100%',
          overflow: 'hidden',
        }}>
          <EnhancedTextField
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            fullWidth
            required
            placeholder="e.g., APT29 SolarWinds Analysis"
            sx={{ mt: 2 }}
          />
          
          <EnhancedTextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={3}
            placeholder="Brief description of this analysis..."
          />
          
          <Box sx={{ 
            p: 2, 
            bgcolor: 'rgba(255, 255, 255, 0.02)', 
            borderRadius: 2,
            border: '1px solid rgba(255, 255, 255, 0.05)'
          }}>
            <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.6)' }}>
              Analysis Summary
            </Typography>
            <Typography 
              variant="body2" 
              sx={{ 
                color: 'rgba(255, 255, 255, 0.8)', 
                mt: 0.5,
                wordBreak: 'break-word',
                overflowWrap: 'break-word',
                maxWidth: '100%',
              }}
            >
              {nodes.length} nodes • {edges.length} edges
              {sourceUrl && ` • Source: ${new URL(sourceUrl).hostname}`}
            </Typography>
          </Box>
        </Box>
        
        {saving && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress 
              sx={{
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: 'rgba(255, 255, 255, 0.7)',
                }
              }}
            />
          </Box>
        )}
      </EnhancedDialogContent>
      
      <EnhancedDialogActions>
        <SecondaryButton 
          onClick={onClose}
          disabled={saving}
        >
          Cancel
        </SecondaryButton>
        <PrimaryButton 
          onClick={handleSave}
          disabled={saving || !title.trim()}
        >
          {saving ? 'Saving...' : 'Save Flow'}
        </PrimaryButton>
      </EnhancedDialogActions>
    </EnhancedDialog>
  );
};

export default SaveFlowDialog;