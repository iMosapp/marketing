/**
 * PickerModals — referral, tag and campaign picker modals.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView, FlatList } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export default function PickerModals(props: any) {
  const {
    s, colors, isEditing,
    showReferralPicker, setShowReferralPicker, contactSearch, setContactSearch, filteredContacts, selectReferrer,
    showTagPicker, setShowTagPicker, tagSearch, setTagSearch, filteredAvailableTags, addTag, addTagFromHero,
    showCampaignPicker, setShowCampaignPicker, availableCampaigns, enrollInCampaign,
  } = props;
  const router = useRouter();

  return (
    <>
      {/* Referral Picker */}
      <Modal visible={showReferralPicker} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowReferralPicker(false)}>
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Select Referrer</Text>
            <View style={{ width: 60 }} />
          </View>
          <View style={s.modalSearch}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput style={s.modalSearchInput} placeholder="Search contacts" placeholderTextColor={colors.textSecondary}
              value={contactSearch} onChangeText={setContactSearch} />
          </View>
          <FlatList data={filteredContacts} keyExtractor={(i: any) => i._id} renderItem={({ item }: any) => (
            <TouchableOpacity style={s.pickerItem} onPress={() => selectReferrer(item)}>
              <View style={s.pickerAvatar}><Text style={s.pickerAvatarText}>{item.first_name?.[0]}{item.last_name?.[0] || ''}</Text></View>
              <View style={{ flex: 1 }}><Text style={s.pickerName}>{item.first_name} {item.last_name || ''}</Text><Text style={s.pickerSub}>{item.phone}</Text></View>
            </TouchableOpacity>
          )} ListEmptyComponent={<View style={s.emptyPicker}><Text style={s.emptyPickerText}>No contacts found</Text></View>} />
        </SafeAreaView>
      </Modal>

      {/* Tag Picker */}
      <Modal visible={showTagPicker} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => { setShowTagPicker(false); setTagSearch(''); }}>
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Select Tag</Text>
            <TouchableOpacity onPress={() => { setShowTagPicker(false); setTagSearch(''); router.push('/settings/tags' as any); }}>
              <Text style={s.modalAction}>Manage</Text>
            </TouchableOpacity>
          </View>
          <View style={s.modalSearch}>
            <Ionicons name="search" size={18} color={colors.textSecondary} />
            <TextInput style={s.modalSearchInput} placeholder="Search tags..." placeholderTextColor={colors.textSecondary}
              value={tagSearch} onChangeText={setTagSearch} autoCapitalize="none" />
          </View>
          <ScrollView style={{ flex: 1 }}>
            {filteredAvailableTags.length > 0 ? filteredAvailableTags.map((tag: any) => (
              <TouchableOpacity key={tag._id} style={s.pickerItem} onPress={() => isEditing ? addTag(tag.name) : addTagFromHero(tag.name)} data-testid={`tag-option-${tag.name}`}>
                <View style={[s.dateRowIcon, { backgroundColor: `${tag.color}20` }]}>
                  <Ionicons name={tag.icon || 'pricetag'} size={18} color={tag.color} />
                </View>
                <View style={{ flex: 1 }}><Text style={s.pickerName}>{tag.name}</Text></View>
                <Ionicons name="add-circle" size={24} color={tag.color} />
              </TouchableOpacity>
            )) : (
              <View style={s.emptyPicker}><Text style={s.emptyPickerText}>No tags available</Text></View>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Campaign Picker */}
      <Modal visible={showCampaignPicker} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowCampaignPicker(false)}>
              <Text style={s.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={s.modalTitle}>Enroll in Campaign</Text>
            <View style={{ width: 60 }} />
          </View>
          <FlatList data={availableCampaigns} keyExtractor={(i: any) => i._id} contentContainerStyle={{ padding: 16 }}
            renderItem={({ item }: any) => (
              <TouchableOpacity style={s.campaignCard} onPress={() => enrollInCampaign(item)}>
                <View style={[s.quickActionIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="calendar" size={20} color="#007AFF" />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={s.campaignName}>{item.name}</Text>
                  <Text style={s.campaignSub}>{item.sequences?.length || 0} steps</Text>
                </View>
                <Ionicons name="add-circle" size={24} color="#007AFF" />
              </TouchableOpacity>
            )} ListEmptyComponent={<View style={s.emptyPicker}><Text style={s.emptyPickerText}>No available campaigns</Text></View>} />
        </SafeAreaView>
      </Modal>
    </>
  );
}
