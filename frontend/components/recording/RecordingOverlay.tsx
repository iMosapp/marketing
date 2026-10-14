import React, { useEffect } from 'react';
import { useRecordingStore } from '../../store/recordingStore';
import { useToast } from '../common/Toast';
import { RecordingBar } from './RecordingBar';
import { RecordingResultSheet } from './RecordingResultSheet';

// Mounted once above the navigator: the recording bar, the saved sheet and the error toast live outside any screen.
export const RecordingOverlay = () => {
  const error = useRecordingStore(s => s.error);
  const clearError = useRecordingStore(s => s.clearError);
  const { showToast } = useToast();
  useEffect(() => {
    if (!error) return;
    showToast(error, 'error', 3500);
    clearError();
  }, [error, showToast, clearError]);
  return (
    <>
      <RecordingBar />
      <RecordingResultSheet />
    </>
  );
};
