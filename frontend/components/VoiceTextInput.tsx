import React from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  TextInputProps,
  Text,
} from 'react-native';
import VoiceInput from './VoiceInput';

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
          placeholderTextColor="#8E8E93"
          {...props}
        />
        {showVoice && (
          <View style={styles.voiceContainer}>
            <VoiceInput
              onTranscription={handleTranscription}
              size="small"
              color="#8E8E93"
            />
          </View>
        )}
      </View>
      {hint && <Text style={styles.hint}>{hint}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  inputWrapper: {
    position: 'relative',
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    paddingRight: 50,
    fontSize: 16,
    color: '#FFF',
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
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
});
