import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  Image,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { Audio } from 'expo-av';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import VoiceInput from '../../components/VoiceInput';
import VoicemailRecorder from '../../components/VoicemailRecorder';

const IS_WEB = Platform.OS === 'web';

const SOCIAL_PLATFORMS = [
  { key: 'facebook', label: 'Facebook', icon: 'logo-facebook', color: '#1877F2', placeholder: 'https://facebook.com/yourprofile' },
  { key: 'instagram', label: 'Instagram', icon: 'logo-instagram', color: '#E4405F', placeholder: 'https://instagram.com/yourhandle' },
  { key: 'linkedin', label: 'LinkedIn', icon: 'logo-linkedin', color: '#0A66C2', placeholder: 'https://linkedin.com/in/yourprofile' },
  { key: 'twitter', label: 'Twitter/X', icon: 'logo-twitter', color: '#1DA1F2', placeholder: 'https://twitter.com/yourhandle' },
  { key: 'tiktok', label: 'TikTok', icon: 'logo-tiktok', color: '#000000', placeholder: 'https://tiktok.com/@yourhandle' },
  { key: 'youtube', label: 'YouTube', icon: 'logo-youtube', color: '#FF0000', placeholder: 'https://youtube.com/@yourchannel' },
];

export default function MyProfileScreen() {
  const router = useRouter();
  const { user, updateUser } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generatingBio, setGeneratingBio] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  
  const [profile, setProfile] = useState({
    name: '',
    phone: '',
    title: '',
    photo_url: '',
    bio: '',
    hobbies: [] as string[],
    family_info: '',
    hometown: '',
    years_experience: '',
    fun_facts: [] as string[],
    personal_motto: '',
    social_links: {} as Record<string, string>,
  });
  
  const [newHobby, setNewHobby] = useState('');
  const [newFunFact, setNewFunFact] = useState('');
  const [showSocialLinks, setShowSocialLinks] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [initialProfile, setInitialProfile] = useState<typeof profile | null>(null);

  // Track unsaved changes
  useEffect(() => {
    if (initialProfile) {
      const changed = JSON.stringify(profile) !== JSON.stringify(initialProfile);
      setHasUnsavedChanges(changed);
    }
  }, [profile, initialProfile]);

  useEffect(() => {
    loadProfile();
  }, [user?._id]);

  const loadProfile = async () => {
    if (!user?._id) {
      setLoading(false);
      return;
    }
    
    try {
      const response = await api.get(`/profile/${user._id}`);
      const data = response.data.user;
      const loadedProfile = {
        name: data.name || '',
        phone: data.phone || '',
        title: data.title || '',
        photo_url: data.photo_url || '',
        bio: data.bio || '',
        hobbies: data.hobbies || [],
        family_info: data.family_info || '',
        hometown: data.hometown || '',
        years_experience: data.years_experience || '',
        fun_facts: data.fun_facts || [],
        personal_motto: data.personal_motto || '',
        social_links: data.social_links || {},
      };
      setProfile(loadedProfile);
      setInitialProfile(loadedProfile);
    } catch (error) {
      console.error('Error loading profile:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveProfile = async () => {
    if (!user?._id) return;
    
    setSaving(true);
    try {
      console.log('Saving profile:', JSON.stringify(profile, null, 2));
      await api.put(`/profile/${user._id}`, profile);
      Alert.alert('Success', 'Profile saved successfully!');
      // Update auth store with new user data
      updateUser({ ...user, name: profile.name, phone: profile.phone, title: profile.title });
      // Reset initial profile to mark as saved
      setInitialProfile(profile);
      setHasUnsavedChanges(false);
    } catch (error) {
      console.error('Error saving profile:', error);
      Alert.alert('Error', 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please grant camera roll access to upload photos');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      uploadPhoto(result.assets[0].base64, result.assets[0].mimeType || 'image/jpeg');
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please grant camera access to take photos');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.5,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      uploadPhoto(result.assets[0].base64, result.assets[0].mimeType || 'image/jpeg');
    }
  };

  const uploadPhoto = async (base64: string, mimeType: string) => {
    if (!user?._id) return;
    
    setUploadingPhoto(true);
    try {
      // Create form data
      const formData = new FormData();
      formData.append('file', {
        uri: `data:${mimeType};base64,${base64}`,
        type: mimeType,
        name: 'profile.jpg',
      } as any);

      // For simplicity, we'll send the base64 directly
      const photoUrl = `data:${mimeType};base64,${base64}`;
      
      await api.put(`/profile/${user._id}`, { photo_url: photoUrl });
      setProfile(prev => ({ ...prev, photo_url: photoUrl }));
      Alert.alert('Success', 'Photo uploaded!');
    } catch (error) {
      console.error('Upload error:', error);
      Alert.alert('Error', 'Failed to upload photo');
    } finally {
      setUploadingPhoto(false);
    }
  };

  const generateBio = async () => {
    if (!user?._id) return;
    
    // Check if we have enough info
    if (!profile.hobbies.length && !profile.family_info && !profile.hometown && !profile.years_experience) {
      Alert.alert(
        'Need More Info',
        'Please fill in some personal details (hobbies, family, hometown, or experience) so we can generate a great bio for you!'
      );
      return;
    }
    
    setGeneratingBio(true);
    try {
      const response = await api.post(`/profile/${user._id}/generate-bio`, {
        name: profile.name,
        title: profile.title,
        hobbies: profile.hobbies,
        family_info: profile.family_info,
        hometown: profile.hometown,
        years_experience: profile.years_experience,
        fun_facts: profile.fun_facts,
        personal_motto: profile.personal_motto,
      });
      
      setProfile(prev => ({ ...prev, bio: response.data.bio }));
      Alert.alert('Bio Generated!', 'Feel free to edit it to make it perfect.');
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to generate bio');
    } finally {
      setGeneratingBio(false);
    }
  };

  const addHobby = () => {
    if (newHobby.trim()) {
      setProfile(prev => ({
        ...prev,
        hobbies: [...prev.hobbies, newHobby.trim()]
      }));
      setNewHobby('');
    }
  };

  const removeHobby = (index: number) => {
    setProfile(prev => ({
      ...prev,
      hobbies: prev.hobbies.filter((_, i) => i !== index)
    }));
  };

  const addFunFact = () => {
    if (newFunFact.trim()) {
      setProfile(prev => ({
        ...prev,
        fun_facts: [...prev.fun_facts, newFunFact.trim()]
      }));
      setNewFunFact('');
    }
  };

  const removeFunFact = (index: number) => {
    setProfile(prev => ({
      ...prev,
      fun_facts: prev.fun_facts.filter((_, i) => i !== index)
    }));
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={styles.headerTitleContainer}>
          <Text style={styles.headerTitle}>My Profile</Text>
          {hasUnsavedChanges && (
            <View style={styles.unsavedBadge}>
              <Text style={styles.unsavedBadgeText}>Unsaved</Text>
            </View>
          )}
        </View>
        <TouchableOpacity 
          onPress={saveProfile} 
          style={[styles.saveButton, hasUnsavedChanges && styles.saveButtonActive]}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <Text style={[styles.saveButtonText, hasUnsavedChanges && styles.saveButtonTextActive]}>
              {hasUnsavedChanges ? 'Save' : 'Saved'}
            </Text>
          )}
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 20}
      >
        <ScrollView 
          style={styles.content} 
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: 150 }}
        >
        {/* Profile Photo Section */}
        <View style={styles.photoSection}>
          <TouchableOpacity 
            style={styles.photoContainer}
            onPress={() => {
              // On web, directly open file picker (no camera option)
              if (IS_WEB) {
                pickImage();
                return;
              }
              Alert.alert(
                'Update Photo',
                'Choose how to update your profile photo',
                [
                  { text: 'Take Photo', onPress: takePhoto },
                  { text: 'Choose from Library', onPress: pickImage },
                  { text: 'Cancel', style: 'cancel' },
                ]
              );
            }}
            disabled={uploadingPhoto}
          >
            {uploadingPhoto ? (
              <View style={styles.photoPlaceholder}>
                <ActivityIndicator size="large" color="#007AFF" />
              </View>
            ) : profile.photo_url ? (
              <Image source={{ uri: profile.photo_url }} style={styles.photo} />
            ) : (
              <View style={styles.photoPlaceholder}>
                <Ionicons name="person" size={48} color="#8E8E93" />
              </View>
            )}
            <View style={styles.photoEditBadge}>
              <Ionicons name="camera" size={16} color="#FFF" />
            </View>
          </TouchableOpacity>
          <Text style={styles.photoHint}>Tap to update photo</Text>
        </View>

        {/* Basic Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>BASIC INFO</Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Full Name</Text>
            <TextInput
              style={styles.input}
              value={profile.name}
              onChangeText={(text) => setProfile(prev => ({ ...prev, name: text }))}
              placeholder="Your name"
              placeholderTextColor="#8E8E93"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Phone Number</Text>
            <TextInput
              style={styles.input}
              value={profile.phone}
              onChangeText={(text) => setProfile(prev => ({ ...prev, phone: text }))}
              placeholder="(555) 123-4567"
              placeholderTextColor="#8E8E93"
              keyboardType="phone-pad"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Job Title</Text>
            <TextInput
              style={styles.input}
              value={profile.title}
              onChangeText={(text) => setProfile(prev => ({ ...prev, title: text }))}
              placeholder="Sales Professional"
              placeholderTextColor="#8E8E93"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Years of Experience</Text>
            <TextInput
              style={styles.input}
              value={profile.years_experience}
              onChangeText={(text) => setProfile(prev => ({ ...prev, years_experience: text }))}
              placeholder="e.g., 5 years"
              placeholderTextColor="#8E8E93"
            />
          </View>
        </View>

        {/* Personal Story Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>YOUR PERSONAL STORY</Text>
          <Text style={styles.sectionSubtitle}>
            This info helps customers connect with you and powers your AI-generated bio
          </Text>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Hometown</Text>
            <TextInput
              style={styles.input}
              value={profile.hometown}
              onChangeText={(text) => setProfile(prev => ({ ...prev, hometown: text }))}
              placeholder="Where are you from?"
              placeholderTextColor="#8E8E93"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Family</Text>
            <TextInput
              style={styles.input}
              value={profile.family_info}
              onChangeText={(text) => setProfile(prev => ({ ...prev, family_info: text }))}
              placeholder="e.g., Married with two kids"
              placeholderTextColor="#8E8E93"
            />
          </View>
          
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Personal Motto</Text>
            <TextInput
              style={styles.input}
              value={profile.personal_motto}
              onChangeText={(text) => setProfile(prev => ({ ...prev, personal_motto: text }))}
              placeholder="What do you live by?"
              placeholderTextColor="#8E8E93"
            />
          </View>

          {/* Hobbies */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Hobbies & Interests</Text>
            <View style={styles.tagInputRow}>
              <TextInput
                style={[styles.input, { flex: 1 }]}
                value={newHobby}
                onChangeText={setNewHobby}
                placeholder="Add a hobby"
                placeholderTextColor="#8E8E93"
                onSubmitEditing={addHobby}
              />
              <TouchableOpacity style={styles.addButton} onPress={addHobby}>
                <Ionicons name="add" size={24} color="#007AFF" />
              </TouchableOpacity>
            </View>
            <View style={styles.tagsContainer}>
              {profile.hobbies.map((hobby, index) => (
                <View key={index} style={styles.tag}>
                  <Text style={styles.tagText}>{hobby}</Text>
                  <TouchableOpacity onPress={() => removeHobby(index)}>
                    <Ionicons name="close-circle" size={18} color="#8E8E93" />
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          </View>

          {/* Fun Facts */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>Fun Facts About You</Text>
            <View style={styles.tagInputRow}>
              <TextInput
                style={[styles.input, { flex: 1 }]}
                value={newFunFact}
                onChangeText={setNewFunFact}
                placeholder="Add a fun fact"
                placeholderTextColor="#8E8E93"
                onSubmitEditing={addFunFact}
              />
              <TouchableOpacity style={styles.addButton} onPress={addFunFact}>
                <Ionicons name="add" size={24} color="#007AFF" />
              </TouchableOpacity>
            </View>
            <View style={styles.tagsContainer}>
              {profile.fun_facts.map((fact, index) => (
                <View key={index} style={styles.tag}>
                  <Text style={styles.tagText}>{fact}</Text>
                  <TouchableOpacity onPress={() => removeFunFact(index)}>
                    <Ionicons name="close-circle" size={18} color="#8E8E93" />
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* AI Bio Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>YOUR BIO</Text>
          <Text style={styles.sectionSubtitle}>
            This appears on your digital business card
          </Text>
          
          <TouchableOpacity 
            style={styles.generateButton}
            onPress={generateBio}
            disabled={generatingBio}
          >
            {generatingBio ? (
              <>
                <ActivityIndicator size="small" color="#FFF" />
                <Text style={styles.generateButtonText}>Generating...</Text>
              </>
            ) : (
              <>
                <Ionicons name="sparkles" size={20} color="#FFF" />
                <Text style={styles.generateButtonText}>Generate My Bio with AI</Text>
              </>
            )}
          </TouchableOpacity>
          
          <View style={styles.voiceInputRow}>
            <TextInput
              style={[styles.input, styles.bioInput, { flex: 1 }]}
              value={profile.bio}
              onChangeText={(text) => setProfile(prev => ({ ...prev, bio: text }))}
              placeholder="Your professional bio will appear here..."
              placeholderTextColor="#8E8E93"
              multiline
              numberOfLines={5}
              textAlignVertical="top"
            />
            <VoiceInput
              onTranscription={(text) => setProfile(prev => ({ ...prev, bio: prev.bio ? prev.bio + ' ' + text : text }))}
              size="medium"
              style={{ marginLeft: 8 }}
            />
          </View>
        </View>

        {/* Social Links Section (moved above voicemail) */}
        <View style={styles.section}>
          <TouchableOpacity 
            style={styles.sectionHeader}
            onPress={() => setShowSocialLinks(!showSocialLinks)}
          >
            <View>
              <Text style={styles.sectionTitle}>SOCIAL MEDIA LINKS</Text>
              <Text style={styles.sectionSubtitle}>
                Connect customers to your profiles
              </Text>
            </View>
            <Ionicons 
              name={showSocialLinks ? 'chevron-up' : 'chevron-down'} 
              size={24} 
              color="#8E8E93" 
            />
          </TouchableOpacity>
          
          {showSocialLinks && (
            <View style={styles.socialLinksContainer}>
              {SOCIAL_PLATFORMS.map((platform) => (
                <View key={platform.key} style={styles.socialInputGroup}>
                  <View style={styles.socialLabel}>
                    <Ionicons name={platform.icon as any} size={20} color={platform.color} />
                    <Text style={styles.socialLabelText}>{platform.label}</Text>
                  </View>
                  <TextInput
                    style={styles.input}
                    value={profile.social_links[platform.key] || ''}
                    onChangeText={(text) => setProfile(prev => ({
                      ...prev,
                      social_links: { ...prev.social_links, [platform.key]: text }
                    }))}
                    placeholder={platform.placeholder}
                    placeholderTextColor="#8E8E93"
                    autoCapitalize="none"
                    keyboardType="url"
                  />
                </View>
              ))}
            </View>
          )}
        </View>

        {/* Voicemail Greeting Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>VOICEMAIL GREETING</Text>
          <Text style={styles.sectionSubtitle}>
            Record a custom voicemail greeting for missed calls
          </Text>
          <VoicemailRecorder />
        </View>

        {/* Preview Card Button */}
        <TouchableOpacity 
          style={styles.previewButton}
          onPress={() => router.push(`/card/${user?._id}`)}
        >
          <Ionicons name="eye" size={20} color="#FFF" />
          <Text style={styles.previewButtonText}>Preview My Digital Card</Text>
        </TouchableOpacity>

        <View style={{ height: 50 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  voiceInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
  },
  headerTitleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  unsavedBadge: {
    backgroundColor: '#FF9500',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  unsavedBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  saveButtonActive: {
    backgroundColor: '#007AFF',
  },
  saveButtonText: {
    fontSize: 17,
    color: '#8E8E93',
    fontWeight: '600',
  },
  saveButtonTextActive: {
    color: '#FFF',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  photoSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  photoContainer: {
    position: 'relative',
  },
  photo: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 3,
    borderColor: '#007AFF',
  },
  photoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#3C3C3E',
  },
  photoEditBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#007AFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#000',
  },
  photoHint: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 8,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#6E6E73',
    marginBottom: 16,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  bioInput: {
    height: 120,
    paddingTop: 14,
  },
  tagInputRow: {
    flexDirection: 'row',
    gap: 8,
  },
  addButton: {
    width: 48,
    height: 48,
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 8,
  },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginRight: 8,
    marginBottom: 8,
    gap: 6,
  },
  tagText: {
    fontSize: 14,
    color: '#FFF',
  },
  generateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#5856D6',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    gap: 8,
  },
  generateButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  socialLinksContainer: {
    marginTop: 16,
  },
  socialInputGroup: {
    marginBottom: 16,
  },
  socialLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  socialLabelText: {
    fontSize: 14,
    color: '#FFF',
  },
  previewButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    gap: 8,
    marginTop: 8,
  },
  previewButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});
