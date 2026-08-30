import 'react-native';

declare module 'react-native' {
  interface ViewProps { dataSet?: Record<string, string>; }
  interface TextProps { dataSet?: Record<string, string>; }
  interface TextInputProps { dataSet?: Record<string, string>; }
  interface TouchableOpacityProps { dataSet?: Record<string, string>; }
  interface PressableProps { dataSet?: Record<string, string>; }
  interface ScrollViewProps { dataSet?: Record<string, string>; }
}
