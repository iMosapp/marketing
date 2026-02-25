import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Alert,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';
import { useToast } from '../../../components/common/Toast';

const IS_WEB = Platform.OS === 'web';

interface Team {
  id: string;
  name: string;
}

export default function NewLeadSourceScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loadingTeams, setLoadingTeams] = useState(true);
  
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    team_id: '',
    assignment_method: 'jump_ball' as 'jump_ball' | 'round_robin' | 'weighted_round_robin',
    is_active: true,
  });

  useEffect(() => {
    if (user?._id) {
      fetchTeams();
    }
  }, [user?._id]);

  const fetchTeams = async () => {
    if (!user?._id) {
      setLoadingTeams(false);
      return;
    }
    
    try {
      console.log('Fetching teams for user:', user._id);
      const response = await api.get(`/admin/team/shared-inboxes?user_id=${user._id}`);
      console.log('Teams response:', response.data);
      
      // Response is an array directly
      const teamsData = Array.isArray(response.data) ? response.data : [];
      const mappedTeams = teamsData.map((t: any) => ({ 
        id: t.id || t._id, 
        name: t.name 
      }));
      console.log('Mapped teams:', mappedTeams);
      setTeams(mappedTeams);
    } catch (error) {
      console.error('Error fetching teams:', error);
      setTeams([]);
    } finally {
      setLoadingTeams(false);
    }
  };


  const handleSave = async () => {
    if (!formData.name.trim()) {
      if (IS_WEB) {
        showToast('Please enter a name for the lead source', 'error');
      } else {
        Alert.alert('Error', 'Please enter a name for the lead source');
      }
      return;
    }
    if (!formData.team_id) {
      if (IS_WEB) {
        showToast('Please select a team to handle leads from this source', 'error');
      } else {
        Alert.alert('Error', 'Please select a team to handle leads from this source');
      }
      return;
    }

    setSaving(true);
    try {
      const storeId = user?.store_id || user?._id;
      const response = await api.post(`/lead-sources?store_id=${storeId}`, formData);
      
      if (response.data.success) {
        if (IS_WEB) {
          showToast(`Lead Source "${formData.name}" created successfully!`, 'success', 4000);
          // Navigate back after a short delay to show the toast
          setTimeout(() => router.back(), 1500);
        } else {
          Alert.alert(
            'Lead Source Created',
            `Webhook URL:\n${response.data.lead_source.webhook_url}\n\nAPI Key has been generated. View details to copy credentials.`,
            [{ text: 'OK', onPress: () => router.back() }]
          );
        }
      }
    } catch (error) {
      console.error('Error creating lead source:', error);
      if (IS_WEB) {
        showToast('Failed to create lead source', 'error');
      } else {
        Alert.alert('Error', 'Failed to create lead source');
      }
    } finally {
      setSaving(false);
    }
  };

  const assignmentMethods = [
    {
      id: 'jump_ball',
      name: 'Jump Ball',
      description: 'First team member to respond claims the lead',
      icon: 'flash',
      color: '#FF9500',
    },
    {
      id: 'round_robin',
      name: 'Round Robin',
      description: 'Auto-assign to next team member in rotation',
      icon: 'sync',
      color: '#007AFF',
    },
    {
      id: 'weighted_round_robin',
      name: 'Weighted Round Robin',
      description: 'Auto-assign to team member with fewest leads',
      icon: 'scale',
      color: '#34C759',
    },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        {IS_WEB ? (
          <button
            type="button"
            onClick={() => router.back()}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8 }}
            data-testid="back-btn"
          >
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </button>
        ) : (
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
        )}
        <Text style={styles.title}>New Lead Source</Text>
        {IS_WEB ? (
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            style={{
              background: 'none',
              border: 'none',
              cursor: saving ? 'not-allowed' : 'pointer',
              padding: 8,
              opacity: saving ? 0.5 : 1,
            }}
            data-testid="create-btn"
          >
            {saving ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <Text style={styles.saveButtonText}>Create</Text>
            )}
          </button>
        ) : (
          <TouchableOpacity
            onPress={handleSave}
            disabled={saving}
            style={styles.saveButton}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#007AFF" />
            ) : (
              <Text style={styles.saveButtonText}>Create</Text>
            )}
          </TouchableOpacity>
        )}
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {/* Name */}
        <View style={styles.section}>
          <Text style={styles.label}>SOURCE NAME</Text>
          <TextInput
            style={styles.input}
            value={formData.name}
            onChangeText={(text) => setFormData({ ...formData, name: text })}
            placeholder="e.g., Facebook Ads, Website Form, RMS Import"
            placeholderTextColor="#6E6E73"
          />
        </View>

        {/* Description */}
        <View style={styles.section}>
          <Text style={styles.label}>DESCRIPTION (OPTIONAL)</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            value={formData.description}
            onChangeText={(text) => setFormData({ ...formData, description: text })}
            placeholder="Describe this lead source..."
            placeholderTextColor="#6E6E73"
            multiline
            numberOfLines={3}
          />
        </View>

        {/* Team Selection */}
        <View style={styles.section}>
          <Text style={styles.label}>ASSIGN TO TEAM</Text>
          {loadingTeams ? (
            <ActivityIndicator size="small" color="#007AFF" />
          ) : teams.length === 0 ? (
            <View style={styles.noTeamsContainer}>
              <Text style={styles.noTeamsText}>No teams found</Text>
              {IS_WEB ? (
                <button
                  type="button"
                  onClick={() => router.push('/admin/shared-inboxes')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                >
                  <Text style={styles.createTeamLink}>Create a team first</Text>
                </button>
              ) : (
                <TouchableOpacity onPress={() => router.push('/admin/shared-inboxes')}>
                  <Text style={styles.createTeamLink}>Create a team first</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : (
            <View style={styles.teamsContainer}>
              {teams.map((team) => (
                IS_WEB ? (
                  <button
                    key={team.id}
                    type="button"
                    onClick={() => setFormData({ ...formData, team_id: team.id })}
                    style={{
                      display: 'flex',
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                      backgroundColor: formData.team_id === team.id ? '#007AFF10' : '#1C1C1E',
                      borderRadius: 10,
                      padding: 14,
                      border: formData.team_id === team.id ? '1px solid #007AFF' : '1px solid #2C2C2E',
                      cursor: 'pointer',
                      marginBottom: 8,
                      width: '100%',
                    }}
                    data-testid={`team-option-${team.id}`}
                  >
                    <Ionicons
                      name={formData.team_id === team.id ? 'radio-button-on' : 'radio-button-off'}
                      size={20}
                      color={formData.team_id === team.id ? '#007AFF' : '#8E8E93'}
                    />
                    <Text style={[
                      styles.teamOptionText,
                      formData.team_id === team.id && styles.teamOptionTextSelected,
                    ]}>
                      {team.name}
                    </Text>
                  </button>
                ) : (
                  <TouchableOpacity
                    key={team.id}
                    style={[
                      styles.teamOption,
                      formData.team_id === team.id && styles.teamOptionSelected,
                    ]}
                    onPress={() => setFormData({ ...formData, team_id: team.id })}
                  >
                    <Ionicons
                      name={formData.team_id === team.id ? 'radio-button-on' : 'radio-button-off'}
                      size={20}
                      color={formData.team_id === team.id ? '#007AFF' : '#8E8E93'}
                    />
                    <Text style={[
                      styles.teamOptionText,
                      formData.team_id === team.id && styles.teamOptionTextSelected,
                    ]}>
                      {team.name}
                    </Text>
                  </TouchableOpacity>
                )
              ))}
            </View>
          )}
        </View>

        {/* Assignment Method */}
        <View style={styles.section}>
          <Text style={styles.label}>ASSIGNMENT METHOD</Text>
          <Text style={styles.sublabel}>How should leads be distributed to team members?</Text>
          <View style={styles.methodsContainer}>
            {assignmentMethods.map((method) => (
              IS_WEB ? (
                <button
                  key={method.id}
                  type="button"
                  onClick={() => setFormData({ ...formData, assignment_method: method.id as any })}
                  style={{
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'center',
                    backgroundColor: '#1C1C1E',
                    borderRadius: 12,
                    padding: 16,
                    border: formData.assignment_method === method.id 
                      ? `2px solid ${method.color}` 
                      : '2px solid #2C2C2E',
                    cursor: 'pointer',
                    marginBottom: 10,
                    width: '100%',
                    gap: 12,
                  }}
                  data-testid={`method-${method.id}`}
                >
                  <View style={[styles.methodIcon, { backgroundColor: method.color + '20' }]}>
                    <Ionicons name={method.icon as any} size={24} color={method.color} />
                  </View>
                  <View style={styles.methodInfo}>
                    <Text style={styles.methodName}>{method.name}</Text>
                    <Text style={styles.methodDescription}>{method.description}</Text>
                  </View>
                  <Ionicons
                    name={formData.assignment_method === method.id ? 'checkmark-circle' : 'ellipse-outline'}
                    size={24}
                    color={formData.assignment_method === method.id ? method.color : '#3A3A3C'}
                  />
                </button>
              ) : (
                <TouchableOpacity
                  key={method.id}
                  style={[
                    styles.methodCard,
                    formData.assignment_method === method.id && styles.methodCardSelected,
                    formData.assignment_method === method.id && { borderColor: method.color },
                  ]}
                  onPress={() => setFormData({ ...formData, assignment_method: method.id as any })}
                >
                  <View style={[styles.methodIcon, { backgroundColor: method.color + '20' }]}>
                    <Ionicons name={method.icon as any} size={24} color={method.color} />
                  </View>
                  <View style={styles.methodInfo}>
                    <Text style={styles.methodName}>{method.name}</Text>
                    <Text style={styles.methodDescription}>{method.description}</Text>
                  </View>
                  <Ionicons
                    name={formData.assignment_method === method.id ? 'checkmark-circle' : 'ellipse-outline'}
                    size={24}
                    color={formData.assignment_method === method.id ? method.color : '#3A3A3C'}
                  />
                </TouchableOpacity>
              )
            ))}
          </View>
        </View>

        {/* Info Box */}
        <View style={styles.infoBox}>
          <Ionicons name="information-circle" size={20} color="#007AFF" />
          <Text style={styles.infoText}>
            After creating this lead source, you'll receive a webhook URL and API key. 
            Use these to send leads from external systems (RMS platforms, ad platforms, landing pages, etc.)
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  saveButton: {
    padding: 4,
  },
  saveButtonText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    letterSpacing: 0.5,
  },
  sublabel: {
    fontSize: 13,
    color: '#6E6E73',
    marginBottom: 12,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  teamsContainer: {
    gap: 8,
  },
  teamOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 14,
    gap: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  teamOptionSelected: {
    borderColor: '#007AFF',
    backgroundColor: '#007AFF10',
  },
  teamOptionText: {
    fontSize: 16,
    color: '#FFF',
  },
  teamOptionTextSelected: {
    color: '#007AFF',
  },
  noTeamsContainer: {
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 20,
    alignItems: 'center',
  },
  noTeamsText: {
    fontSize: 15,
    color: '#8E8E93',
    marginBottom: 8,
  },
  createTeamLink: {
    fontSize: 15,
    color: '#007AFF',
    fontWeight: '600',
  },
  methodsContainer: {
    gap: 12,
  },
  methodCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    borderWidth: 2,
    borderColor: '#2C2C2E',
  },
  methodCardSelected: {
    backgroundColor: '#1C1C1E',
  },
  methodIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  methodInfo: {
    flex: 1,
  },
  methodName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 2,
  },
  methodDescription: {
    fontSize: 13,
    color: '#8E8E93',
  },
  infoBox: {
    flexDirection: 'row',
    backgroundColor: '#007AFF15',
    borderRadius: 10,
    padding: 14,
    gap: 10,
    marginTop: 8,
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: '#007AFF',
    lineHeight: 18,
  },
});
