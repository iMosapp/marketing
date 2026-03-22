import React from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  TextInputProps,
  Text,
} from 'react-native';
import VoiceInput from './VoiceInput';

import { useThemeStore } from '../store/themeStore';
interface VoiceTextInputProps extends TextInputProps {
  value: string;
  onChangeText: (text: string) => void;
  label?: string;
  hint?: string;
  showVoice?: boolean;
  voiceAppend?: boolean; // If true, appends to existing text. If false, replaces.
}

/**
 * TextInput with integrated voice-to-text button
 * 
 * Usage:
 * <VoiceTextInput
 *   label="About You"
 *   value={bio}
 *   onChangeText={setBio}
 *   placeholder="Tell us about yourself..."
 *   multiline
 * />
 */
export default function VoiceTextInput({
  value,
  onChangeText,
  label,
  hint,
  showVoice = true,
  voiceAppend = true,
  style,
  ...props
}: VoiceTextInputProps) {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const handleTranscription = (text: string) => {
    if (voiceAppend && value) {
      onChangeText(value + ' ' + text);
    } else {
      onChangeText(text);
    }
  };

  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={styles.inputWrapper}>
        <TextInput
          style={[
            styles.input,
            props.multiline && styles.multilineInput,
            showVoice && styles.inputWithVoice,
            style,
          ]}
          value={value}
          onChangeText={onChangeText}
          placeholderTextColor={colors.textSecondary}
          {...props}
        />
        {showVoice && (
          <View style={styles.voiceContainer}>
            <VoiceInput
              onTranscription={handleTranscription}
              size="small"
              color={colors.textSecondary}
            />
          </View>
        )}
      </View>
      {hint && <Text style={styles.hint}>{hint}</Text>}
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  inputWrapper: {
    position: 'relative',
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    paddingRight: 50,
    fontSize: 18,
    color: colors.text,
  },
  inputWithVoice: {
    paddingRight: 50,
  },
  multilineInput: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  voiceContainer: {
    position: 'absolute',
    right: 8,
    top: 8,
    bottom: 8,
    justifyContent: 'center',
  },
  hint: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
});
