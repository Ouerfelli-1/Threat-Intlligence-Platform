import {
  EnhancedDialog,
  EnhancedDialogContent,
  EnhancedDialogActions,
  SecondaryButton,
  PrimaryButton,
} from '../../../shared/components/EnhancedDialog';
import {
  FlowDialogContent,
} from '../../../shared/components/Typography';

interface NewSearchDialogProps {
  open: boolean;
  hasUnsavedChanges: boolean;
  onClose: () => void;
  onConfirm: () => void;
  onSaveFirst: () => void;
}

export default function NewSearchDialog({
  open,
  hasUnsavedChanges,
  onClose,
  onConfirm,
  onSaveFirst,
}: NewSearchDialogProps) {
  return (
    <EnhancedDialog
      open={open}
      onClose={onClose}
      title="Start New Analysis?"
      size="small"
    >
      <EnhancedDialogContent>
        <FlowDialogContent>
          {hasUnsavedChanges ? (
            <>
              You have unsaved changes to your current analysis. 
              Would you like to save before starting a new analysis?
            </>
          ) : (
            <>
              This will clear your current analysis and return you to the search screen. 
              Your current visualization will be lost.
            </>
          )}
        </FlowDialogContent>
      </EnhancedDialogContent>
      
      <EnhancedDialogActions>
        {hasUnsavedChanges ? (
          <>
            <SecondaryButton onClick={onClose}>
              Cancel
            </SecondaryButton>
            
            <SecondaryButton onClick={onConfirm}>
              Don't Save
            </SecondaryButton>
            
            <PrimaryButton onClick={onSaveFirst}>
              Save First
            </PrimaryButton>
          </>
        ) : (
          <>
            <SecondaryButton onClick={onClose}>
              Cancel
            </SecondaryButton>
            
            <PrimaryButton onClick={onConfirm}>
              Start New Search
            </PrimaryButton>
          </>
        )}
      </EnhancedDialogActions>
    </EnhancedDialog>
  );
}