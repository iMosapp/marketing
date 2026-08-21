/**
 * DateModals — automation edit, date picker & custom date label modals.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView, Platform } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { format } from 'date-fns';
import { formatDateUTC } from '../../utils/contactHelpers';

const IS_WEB = Platform.OS === 'web';
const getDaysInMonth = (m: number, y: number) => new Date(y, m + 1, 0).getDate();
const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];

export default function DateModals(props: any) {
  const {
    s, colors, mode,
    editingAutomation, setEditingAutomation, automationPickerDate, setAutomationPickerDate,
    handleClearAutomation, handleUpdateAutomationDate,
    showDatePicker, setShowDatePicker, activeDateLabel, tempDate, handleDateChange, confirmDateSelection,
    webMonth, setWebMonth, webDay, setWebDay, webYear, setWebYear,
    showCustomDateLabel, setShowCustomDateLabel, pendingCustomDate,
    newCustomDateName, setNewCustomDateName, confirmCustomDateWithLabel,
  } = props;

  return (
    <>
      {/* Automation Edit Modal */}
      {editingAutomation && (
        <Modal visible={!!editingAutomation} animationType="fade" transparent onRequestClose={() => setEditingAutomation(null)}>
          <TouchableOpacity style={s.labelOverlay} activeOpacity={1} onPress={() => setEditingAutomation(null)}>
            <TouchableOpacity activeOpacity={1} style={s.labelModal} onPress={() => {}}>
              <Text style={s.labelTitle}>Edit {editingAutomation.label}</Text>
              <Text style={[s.labelSub, { color: editingAutomation.color }]}>
                {editingAutomation.value ? formatDateUTC(editingAutomation.value, 'MMM d, yyyy') : 'No date set'}
              </Text>
              {IS_WEB ? (
                <input
                  type="date"
                  defaultValue={editingAutomation.value ? new Date(editingAutomation.value).toISOString().split('T')[0] : ''}
                  onChange={(e: any) => {
                    if (e.target.value) setAutomationPickerDate(new Date(e.target.value + 'T12:00:00'));
                  }}
                  style={{
                    width: '100%', padding: 12, borderRadius: 10,
                    backgroundColor: colors.surface, color: colors.text, border: '1px solid #3A3A3C',
                    fontSize: 18, marginBottom: 12, marginTop: 8,
                  }}
                  data-testid="automation-date-input"
                />
              ) : (
                <DateTimePicker
                  value={editingAutomation.value ? new Date(editingAutomation.value) : new Date()}
                  mode="date"
                  display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                  onChange={(_: any, d?: Date) => { if (d) setAutomationPickerDate(d); }}
                  textColor={colors.text}
                  themeVariant={mode}
                  style={{ height: 150, marginVertical: 8 }}
                />
              )}
              <View style={{ flexDirection: 'row', gap: 12, marginTop: 4 }}>
                <TouchableOpacity
                  style={[s.labelBtn, { backgroundColor: colors.surface }]}
                  onPress={() => handleClearAutomation(editingAutomation.field)}
                  data-testid="automation-clear-btn"
                >
                  <Text style={{ fontSize: 18, fontWeight: '600', color: '#FF3B30' }}>Clear Date</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.labelBtn, { backgroundColor: editingAutomation.color || '#007AFF' }]}
                  onPress={() => handleUpdateAutomationDate(editingAutomation.field, automationPickerDate)}
                  data-testid="automation-save-btn"
                >
                  <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>Save Date</Text>
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          </TouchableOpacity>
        </Modal>
      )}

      {/* Date Picker */}
      {showDatePicker && (
        <Modal visible={showDatePicker} animationType={IS_WEB ? 'none' : 'slide'} transparent onRequestClose={() => setShowDatePicker(false)}>
          <View style={s.dateOverlay}>
            <TouchableOpacity style={{ flex: 1 }} activeOpacity={1} onPress={() => setShowDatePicker(false)} />
            <View style={[s.dateModal, IS_WEB && { minHeight: 400 }]}>
              <View style={s.dateModalHeader}>
                <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                  <Text style={{ fontSize: 18, color: '#FF3B30' }}>Cancel</Text>
                </TouchableOpacity>
                <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>{activeDateLabel}</Text>
                <TouchableOpacity onPress={confirmDateSelection}>
                  <Text style={{ fontSize: 18, fontWeight: '600', color: '#007AFF' }}>Done</Text>
                </TouchableOpacity>
              </View>
              {IS_WEB ? (
                <View style={{ flexDirection: 'row', paddingHorizontal: 20, paddingVertical: 16, gap: 12 }}>
                  {/* Month */}
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={s.webPickerLabel}>MONTH</Text>
                    <ScrollView style={s.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {months.map((m, i) => (
                        <TouchableOpacity key={m} style={[s.webPickerItem, webMonth === i && s.webPickerItemSel]}
                          onPress={() => { setWebMonth(i); const max = getDaysInMonth(i, webYear); if (webDay > max) setWebDay(max); }}>
                          <Text style={[s.webPickerText, webMonth === i && s.webPickerTextSel]}>{m}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                  {/* Day */}
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={s.webPickerLabel}>DAY</Text>
                    <ScrollView style={s.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {Array.from({ length: getDaysInMonth(webMonth, webYear) }, (_, i) => i + 1).map(d => (
                        <TouchableOpacity key={d} style={[s.webPickerItem, webDay === d && s.webPickerItemSel]}
                          onPress={() => setWebDay(d)}>
                          <Text style={[s.webPickerText, webDay === d && s.webPickerTextSel]}>{d}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                  {/* Year */}
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={s.webPickerLabel}>YEAR</Text>
                    <ScrollView style={s.webPickerScroll} showsVerticalScrollIndicator={false}>
                      {Array.from({ length: 126 }, (_, i) => 1920 + i).map(y => (
                        <TouchableOpacity key={y} style={[s.webPickerItem, webYear === y && s.webPickerItemSel]}
                          onPress={() => { setWebYear(y); const max = getDaysInMonth(webMonth, y); if (webDay > max) setWebDay(max); }}>
                          <Text style={[s.webPickerText, webYear === y && s.webPickerTextSel]}>{y}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                </View>
              ) : (
                <DateTimePicker value={tempDate} mode="date" display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                  onChange={handleDateChange} textColor={colors.text} themeVariant={mode} style={{ height: 200, marginHorizontal: 10 }}
                  maximumDate={new Date(2100, 11, 31)} minimumDate={new Date(1900, 0, 1)} />
              )}
              {(Platform.OS === 'ios' || IS_WEB) && (
                <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 16 }}>
                  <TouchableOpacity style={s.dateConfirmBtn} onPress={confirmDateSelection}>
                    <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>
                      Select {IS_WEB ? format(new Date(webYear, webMonth, webDay), 'MMM d, yyyy') : format(tempDate, 'MMM d, yyyy')}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          </View>
        </Modal>
      )}

      {/* Custom Date Label Modal */}
      <Modal visible={showCustomDateLabel} animationType="fade" transparent onRequestClose={() => setShowCustomDateLabel(false)}>
        <TouchableOpacity style={s.labelOverlay} activeOpacity={1} onPress={() => setShowCustomDateLabel(false)}>
          <TouchableOpacity activeOpacity={1} style={s.labelModal} onPress={() => {}}>
            <Text style={s.labelTitle}>Name This Date</Text>
            <Text style={s.labelSub}>{pendingCustomDate ? format(pendingCustomDate, 'MMM d, yyyy') : ''}</Text>
            <TextInput style={s.labelInput} placeholder='e.g., "Lease Expiration"' placeholderTextColor={colors.textSecondary}
              value={newCustomDateName} onChangeText={setNewCustomDateName} returnKeyType="done" onSubmitEditing={confirmCustomDateWithLabel} />
            <View style={{ flexDirection: 'row', gap: 12 }}>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: colors.surface }]} onPress={() => setShowCustomDateLabel(false)}>
                <Text style={{ fontSize: 18, fontWeight: '600', color: '#FF3B30' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.labelBtn, { backgroundColor: '#007AFF' }]} onPress={confirmCustomDateWithLabel}>
                <Text style={{ fontSize: 18, fontWeight: '600', color: colors.text }}>Save</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </>
  );
}
