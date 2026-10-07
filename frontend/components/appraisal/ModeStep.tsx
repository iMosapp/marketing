import React from 'react';
import { View, Text } from 'react-native';
import { BigButton, StepTitle } from './shared';

type Props = { colors: any; mode: string; onPick: (mode: 'vehicle_here' | 'customer_sent') => void; busy?: boolean };

// Where is the car? Same pipeline either way; this only decides which buttons lead and how media is tagged.
export const ModeStep = ({ colors, mode, onPick, busy }: Props) => (
  <View style={{ gap: 12 }}>
    <StepTitle colors={colors} title="Where is the vehicle?" sub="Both paths run through the same VIN, mileage and inspection steps. This just sets how you capture." />
    <BigButton colors={colors} icon="car-sport" label="Vehicle is here" sub="Scan the VIN and odometer, then walk around it with the phone" onPress={() => onPick('vehicle_here')} primary={mode === 'vehicle_here'} disabled={busy} testId="mode-vehicle-here" />
    <BigButton colors={colors} icon="cloud-upload-outline" label="Customer sent media" sub="Import the VIN photo, odometer photo, pictures and walkaround video they texted or emailed" onPress={() => onPick('customer_sent')} primary={mode === 'customer_sent'} disabled={busy} testId="mode-customer-sent" />
    <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>Customer not here and nothing sent yet? Use the trade link above: they photograph the VIN sticker and odometer and add pictures from their own phone.</Text>
  </View>
);
