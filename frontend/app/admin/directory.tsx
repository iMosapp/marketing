import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TextInput,
  RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import api from '../../services/api';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { WebModal } from '../../components/WebModal';

type TabType = 'directory' | 'leaderboard' | 'efficiency' | 'resellers';

interface TeamMember {
  id: string;
  first_name: string;
  last_name: string;
  name?: string;
  email: string;
  phone?: string;
  role: string;
  role_label: string;
  title?: string;
  department?: string;
  company_name?: string;
  commission_percent?: number;
  hourly_rate?: number;
  avatar_url?: string;
  is_active: boolean;
  metrics: {
    quotes_sent: number;
    quotes_accepted: number;
    total_revenue: number;
    avg_deal_size: number;
    avg_days_to_close: number;
    avg_discount_percent: number;
    total_commission_earned: number;
  };
  current_week_kpi?: {
    hours_worked: number;
    demos_done: number;
    earnings_per_hour: number;
  };
  score?: number;
  // Efficiency leaderboard fields
  hours_worked?: number;
  demos_done?: number;
  earnings_per_hour?: number;
  total_earnings?: number;
  trophy?: 'gold' | 'silver' | 'bronze' | null;
}

interface Stats {
  total_members: number;
  by_role: Record<string, number>;
  role_labels: Record<string, string>;
  performance: {
    total_revenue: number;
    total_quotes_sent: number;
    total_quotes_accepted: number;
    overall_conversion_rate: number;
    avg_deal_size: number;
    avg_days_to_close: number;
    total_commission_paid: number;
  };
}

const ROLE_COLORS: Record<string, string> = {
  partner: '#FF9500',
  reseller: '#5856D6',
  support: '#34C759',
  billing: '#007AFF',
  admin: '#FF3B30',
  dev: '#30B0C7',
  sales: '#FF2D55',
  csm: '#AF52DE',
};

const ROLE_ICONS: Record<string, string> = {
  partner: 'people-circle',
  reseller: 'storefront',
  support: 'headset',
  billing: 'card',
  admin: 'shield-checkmark',
  dev: 'code-slash',
  sales: 'trending-up',
  csm: 'people',
};

export default function DirectoryPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('directory');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  
  // Data
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [leaderboard, setLeaderboard] = useState<TeamMember[]>([]);
  const [leaderboardMetric, setLeaderboardMetric] = useState('total_revenue');
  const [efficiencyLeaderboard, setEfficiencyLeaderboard] = useState<TeamMember[]>([]);
  
  // Modals
  const [showAddMember, setShowAddMember] = useState(false);
  const [showMemberDetail, setShowMemberDetail] = useState(false);
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);
  const [showKPIModal, setShowKPIModal] = useState(false);
  const [kpiMember, setKpiMember] = useState<TeamMember | null>(null);
  
  // KPI Form
  const [kpiHours, setKpiHours] = useState('');
  const [kpiDemos, setKpiDemos] = useState('');
  
  // New member form
  const [newMember, setNewMember] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    role: 'sales',
    title: '',
    company_name: '',
    commission_percent: 0,
    hourly_rate: 0,
  });

  useEffect(() => {
    loadData();
  }, [activeTab, selectedRole, leaderboardMetric]);

  const loadData = async () => {
    try {
      if (activeTab === 'directory') {
        const params = new URLSearchParams();
        if (selectedRole) params.append('role', selectedRole);
        if (searchQuery) params.append('search', searchQuery);
        
        const [membersRes, statsRes] = await Promise.all([
          api.get(`/directory/members?${params.toString()}`),
          api.get('/directory/stats/overview'),
        ]);
        setMembers(membersRes.data);
        setStats(statsRes.data);
      } else if (activeTab === 'leaderboard') {
        const res = await api.get(`/directory/leaderboard?metric=${leaderboardMetric}&limit=20`);
        setLeaderboard(res.data.leaderboard);
      } else if (activeTab === 'efficiency') {
        const res = await api.get('/directory/leaderboard/efficiency?period=current_week');
        setEfficiencyLeaderboard(res.data.leaderboard);
      } else if (activeTab === 'resellers') {
        const res = await api.get('/directory/resellers');
        setMembers(res.data);
      }
    } catch (error) {
      console.error('Error loading directory:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    loadData();
  };

  const handleSearch = () => {
    setLoading(true);
    loadData();
  };

  const handleSubmitKPI = async () => {
    if (!kpiMember || !kpiHours) {
      showSimpleAlert('Error', 'Hours worked is required');
      return;
    }
    
    try {
      const result = await api.post(`/directory/members/${kpiMember.id}/kpi`, {
        hours_worked: parseFloat(kpiHours),
        demos_done: parseInt(kpiDemos) || 0,
      });
      
      showSimpleAlert('Success', `KPI submitted! Earnings: $${result.data.earnings_per_hour}/hr`);
      setShowKPIModal(false);
      setKpiHours('');
      setKpiDemos('');
      setKpiMember(null);
      loadData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to submit KPI');
    }
  };

  const openKPIModal = (member: TeamMember) => {
    setKpiMember(member);
    setShowKPIModal(true);
  };

  const handleAddMember = async () => {
    if (!newMember.first_name || !newMember.email) {
      showSimpleAlert('Error', 'Name and email are required');
      return;
    }
    
    try {
      await api.post('/directory/members', newMember);
      showSimpleAlert('Success', 'Team member added');
      setShowAddMember(false);
      setNewMember({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        role: 'sales',
        title: '',
        company_name: '',
        commission_percent: 0,
      });
      loadData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to add member');
    }
  };

  const handleViewMember = async (member: TeamMember) => {
    try {
      const res = await api.get(`/directory/members/${member.id}`);
      setSelectedMember(res.data);
      setShowMemberDetail(true);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to load member details');
    }
  };

  const handleToggleUserActive = (member: TeamMember) => {
    const newStatus = !member.is_active;
    showConfirm(
      newStatus ? 'Activate User' : 'Deactivate User',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} ${member.first_name || member.name || 'this user'}?`,
      async () => {
        try {
          await api.put(`/admin/users/${member.id}`, { is_active: newStatus });
          loadData();
          showSimpleAlert('Success', `User ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update user status');
        }
      },
      undefined,
      newStatus ? 'Activate' : 'Deactivate',
      'Cancel'
    );
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#34C759';
    if (score >= 60) return '#FF9500';
    if (score >= 40) return '#FF9500';
    return '#FF3B30';
  };

  const renderStatsCards = () => {
    if (!stats) return null;
    
    return (
      <View style={styles.statsContainer}>
        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{stats.total_members}</Text>
            <Text style={styles.statLabel}>Team Members</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={[styles.statValue, { color: '#34C759' }]}>
              {formatCurrency(stats.performance.total_revenue)}
            </Text>
            <Text style={styles.statLabel}>Total Revenue</Text>
          </View>
        </View>
        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{stats.performance.overall_conversion_rate}%</Text>
            <Text style={styles.statLabel}>Conversion Rate</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{stats.performance.avg_days_to_close}</Text>
            <Text style={styles.statLabel}>Avg Days to Close</Text>
          </View>
        </View>
      </View>
    );
  };

  const renderRoleFilters = () => {
    const roles = ['partner', 'reseller', 'support', 'billing', 'admin', 'dev', 'sales', 'csm'];
    
    return (
      <ScrollView 
        horizontal 
        showsHorizontalScrollIndicator={false}
        style={styles.roleFilterContainer}
        contentContainerStyle={styles.roleFilterContent}
      >
        <TouchableOpacity
          style={[styles.roleChip, !selectedRole && styles.roleChipActive]}
          onPress={() => setSelectedRole(null)}
        >
          <Text style={[styles.roleChipText, !selectedRole && styles.roleChipTextActive]}>All</Text>
        </TouchableOpacity>
        {roles.map((role) => (
          <TouchableOpacity
            key={role}
            style={[
              styles.roleChip, 
              selectedRole === role && styles.roleChipActive,
              selectedRole === role && { backgroundColor: ROLE_COLORS[role] }
            ]}
            onPress={() => setSelectedRole(role === selectedRole ? null : role)}
          >
            <Ionicons 
              name={ROLE_ICONS[role] as any} 
              size={14} 
              color={selectedRole === role ? '#FFF' : ROLE_COLORS[role]} 
            />
            <Text style={[
              styles.roleChipText, 
              selectedRole === role && styles.roleChipTextActive
            ]}>
              {role.toUpperCase()}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    );
  };

  const renderMemberCard = (member: TeamMember, showScore = false) => (
    <TouchableOpacity
      key={member.id}
      style={styles.memberCard}
      onPress={() => handleViewMember(member)}
      data-testid={`member-${member.id}`}
    >
      <View style={styles.memberHeader}>
        <View style={[styles.avatar, { backgroundColor: ROLE_COLORS[member.role] + '30' }]}>
          <Text style={[styles.avatarText, { color: ROLE_COLORS[member.role] }]}>
            {(member.first_name || member.name || '?')[0]}{(member.last_name || '')[0] || ''}
          </Text>
        </View>
        <View style={styles.memberInfo}>
          <Text style={styles.memberName}>{member.first_name || member.name || 'Unknown'} {member.last_name || ''}</Text>
          <Text style={styles.memberTitle}>{member.title || member.role_label}</Text>
          {member.company_name && (
            <Text style={styles.memberCompany}>{member.company_name}</Text>
          )}
        </View>
        <View style={styles.memberBadges}>
          <View style={[styles.roleBadge, { backgroundColor: ROLE_COLORS[member.role] + '20' }]}>
            <Text style={[styles.roleBadgeText, { color: ROLE_COLORS[member.role] }]}>
              {member.role_label}
            </Text>
          </View>
          {showScore && member.score !== undefined && (
            <View style={[styles.scoreBadge, { backgroundColor: getScoreColor(member.score) + '20' }]}>
              <Text style={[styles.scoreText, { color: getScoreColor(member.score) }]}>
                {member.score}
              </Text>
            </View>
          )}
        </View>
      </View>
      
      <View style={styles.memberMetrics}>
        <View style={styles.metricItem}>
          <Text style={styles.metricValue}>{formatCurrency(member.metrics.total_revenue)}</Text>
          <Text style={styles.metricLabel}>Revenue</Text>
        </View>
        <View style={styles.metricItem}>
          <Text style={styles.metricValue}>{member.metrics.quotes_accepted}/{member.metrics.quotes_sent}</Text>
          <Text style={styles.metricLabel}>Deals</Text>
        </View>
        <View style={styles.metricItem}>
          <Text style={styles.metricValue}>{member.metrics.avg_days_to_close || '-'}</Text>
          <Text style={styles.metricLabel}>Avg Days</Text>
        </View>
        {member.commission_percent !== undefined && member.commission_percent > 0 && (
          <View style={styles.metricItem}>
            <Text style={[styles.metricValue, { color: '#5856D6' }]}>{member.commission_percent}%</Text>
            <Text style={styles.metricLabel}>Commission</Text>
          </View>
        )}
      </View>
      
      {/* User Status Badge */}
      <View style={styles.memberFooter}>
        <TouchableOpacity 
          style={[styles.statusBadge, { backgroundColor: member.is_active !== false ? '#34C75920' : '#FF3B3020' }]}
          onPress={(e) => {
            e.stopPropagation();
            handleToggleUserActive(member);
          }}
          data-testid={`user-status-${member.id}`}
        >
          <View style={[styles.statusDot, { backgroundColor: member.is_active !== false ? '#34C759' : '#FF3B30' }]} />
          <Text style={[styles.statusText, { color: member.is_active !== false ? '#34C759' : '#FF3B30' }]}>
            {member.is_active !== false ? 'Active' : 'Inactive'}
          </Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );

  const renderLeaderboard = () => {
    const metrics = [
      { key: 'total_revenue', label: 'Revenue' },
      { key: 'quotes_accepted', label: 'Deals' },
      { key: 'avg_deal_size', label: 'Deal Size' },
      { key: 'avg_days_to_close', label: 'Speed' },
    ];
    
    return (
      <View style={styles.tabContent}>
        <View style={styles.metricToggle}>
          {metrics.map((m) => (
            <TouchableOpacity
              key={m.key}
              style={[styles.metricButton, leaderboardMetric === m.key && styles.metricButtonActive]}
              onPress={() => setLeaderboardMetric(m.key)}
            >
              <Text style={[styles.metricButtonText, leaderboardMetric === m.key && styles.metricButtonTextActive]}>
                {m.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        
        {leaderboard.map((member, index) => (
          <View key={member.id} style={styles.leaderRow}>
            <View style={[
              styles.rankBadge,
              index === 0 && styles.rankGold,
              index === 1 && styles.rankSilver,
              index === 2 && styles.rankBronze,
            ]}>
              <Text style={styles.rankText}>{index + 1}</Text>
            </View>
            <View style={[styles.avatar, { backgroundColor: ROLE_COLORS[member.role] + '30', width: 40, height: 40 }]}>
              <Text style={[styles.avatarText, { color: ROLE_COLORS[member.role], fontSize: 14 }]}>
                {member.name?.split(' ').map(n => n[0]).join('')}
              </Text>
            </View>
            <View style={styles.leaderInfo}>
              <Text style={styles.leaderName}>{member.name}</Text>
              <Text style={styles.leaderRole}>{member.role_label}</Text>
            </View>
            <View style={styles.leaderValue}>
              <Text style={styles.leaderValueText}>
                {leaderboardMetric === 'total_revenue' || leaderboardMetric === 'avg_deal_size'
                  ? formatCurrency(member.metric_value)
                  : leaderboardMetric === 'avg_days_to_close'
                  ? `${member.metric_value} days`
                  : member.metric_value}
              </Text>
            </View>
          </View>
        ))}
      </View>
    );
  };

  const renderDirectoryTab = () => (
    <View style={styles.tabContent}>
      {renderStatsCards()}
      
      {/* Search */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#8E8E93" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name, email, company..."
          placeholderTextColor="#8E8E93"
          value={searchQuery}
          onChangeText={setSearchQuery}
          onSubmitEditing={handleSearch}
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => { setSearchQuery(''); loadData(); }}>
            <Ionicons name="close-circle" size={20} color="#8E8E93" />
          </TouchableOpacity>
        )}
      </View>
      
      {renderRoleFilters()}
      
      {/* Members List */}
      {members.map((member) => renderMemberCard(member))}
      
      {members.length === 0 && !loading && (
        <View style={styles.emptyState}>
          <Ionicons name="people-outline" size={64} color="#2C2C2E" />
          <Text style={styles.emptyText}>No team members found</Text>
        </View>
      )}
    </View>
  );

  const renderResellersTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Partners & Resellers</Text>
        <Text style={styles.sectionSubtitle}>Performance & Commission Tracking</Text>
      </View>
      
      {members.map((member) => renderMemberCard(member, true))}
    </View>
  );

  const renderEfficiencyTab = () => (
    <View style={styles.tabContent}>
      {efficiencyLeaderboard.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="time-outline" size={64} color="#2C2C2E" />
          <Text style={styles.emptyText}>No KPIs submitted this week</Text>
          <Text style={styles.emptySubtext}>Team members need to log their hours</Text>
        </View>
      ) : (
        efficiencyLeaderboard.map((member, index) => (
          <View key={member.id} style={styles.memberCard}>
            {/* Header with Avatar, Name, and Top Performer Badge */}
            <View style={styles.memberHeader}>
              <View style={[styles.avatar, { backgroundColor: ROLE_COLORS[member.role] + '30' }]}>
                <Text style={[styles.avatarText, { color: ROLE_COLORS[member.role] }]}>
                  {member.name?.split(' ').map(n => n[0]).join('')}
                </Text>
              </View>
              <View style={styles.memberInfo}>
                <Text style={styles.memberName}>{member.name}</Text>
                <Text style={styles.memberTitle}>{member.role_label}</Text>
              </View>
              <View style={styles.memberBadges}>
                {/* Top Performer Badge for #1 */}
                {index === 0 ? (
                  <View style={styles.mvpBadge}>
                    <Ionicons name="star" size={14} color="#000" />
                    <Text style={styles.mvpBadgeText}>#1</Text>
                  </View>
                ) : (
                  <View style={[
                    styles.rankBadgeLarge,
                    index === 1 && styles.rankSilverBg,
                    index === 2 && styles.rankBronzeBg,
                  ]}>
                    <Text style={styles.rankBadgeText}>#{index + 1}</Text>
                  </View>
                )}
              </View>
            </View>
            
            {/* Metrics Row */}
            <View style={styles.memberMetrics}>
              <View style={styles.metricItem}>
                <Text style={[
                  styles.metricValue, 
                  styles.earningsHighlight,
                  index === 0 && { color: '#FFD700' },
                  index === 1 && { color: '#C0C0C0' },
                  index === 2 && { color: '#CD7F32' },
                ]}>
                  ${member.earnings_per_hour}
                </Text>
                <Text style={styles.metricLabel}>Per Hour</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={styles.metricValue}>{member.hours_worked}</Text>
                <Text style={styles.metricLabel}>Hours</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={styles.metricValue}>{member.demos_done}</Text>
                <Text style={styles.metricLabel}>Demos</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={styles.metricValue}>${member.total_earnings || 0}</Text>
                <Text style={styles.metricLabel}>Total</Text>
              </View>
            </View>
          </View>
        ))
      )}
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Company Directory</Text>
        <TouchableOpacity onPress={() => setShowAddMember(true)}>
          <Ionicons name="person-add" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabBarContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabBarContent}>
          {[
            { key: 'directory', label: 'Directory', icon: 'people' },
            { key: 'efficiency', label: '$/Hour', icon: 'trophy' },
            { key: 'leaderboard', label: 'Revenue', icon: 'bar-chart' },
            { key: 'resellers', label: 'Resellers', icon: 'storefront' },
          ].map((tab) => (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, activeTab === tab.key && styles.activeTab]}
              onPress={() => { setActiveTab(tab.key as TabType); setLoading(true); }}
            >
              <Ionicons 
                name={tab.icon as any} 
                size={18} 
                color={activeTab === tab.key ? '#007AFF' : '#8E8E93'} 
              />
              <Text style={[styles.tabText, activeTab === tab.key && styles.activeTabText]}>
                {tab.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {loading ? (
          <ActivityIndicator color="#007AFF" style={{ marginTop: 40 }} />
        ) : (
          <>
            {activeTab === 'directory' && renderDirectoryTab()}
            {activeTab === 'efficiency' && renderEfficiencyTab()}
            {activeTab === 'leaderboard' && renderLeaderboard()}
            {activeTab === 'resellers' && renderResellersTab()}
          </>
        )}
        
        <View style={{ height: 40 }} />
      </ScrollView>

      {/* KPI Input Modal */}
      <WebModal visible={showKPIModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Log Weekly KPIs</Text>
              <TouchableOpacity onPress={() => setShowKPIModal(false)}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            {kpiMember && (
              <View style={styles.modalBody}>
                <View style={styles.kpiMemberInfo}>
                  <View style={[styles.avatar, { backgroundColor: ROLE_COLORS[kpiMember.role] + '30' }]}>
                    <Text style={[styles.avatarText, { color: ROLE_COLORS[kpiMember.role] }]}>
                      {(kpiMember.first_name || kpiMember.name || '?')[0]}{(kpiMember.last_name || '')[0] || ''}
                    </Text>
                  </View>
                  <View>
                    <Text style={styles.kpiMemberName}>{kpiMember.first_name || kpiMember.name || 'Unknown'} {kpiMember.last_name || ''}</Text>
                    <Text style={styles.kpiMemberRole}>{kpiMember.role_label}</Text>
                  </View>
                </View>
                
                <Text style={styles.inputLabel}>Hours Worked This Week *</Text>
                <TextInput
                  style={styles.input}
                  value={kpiHours}
                  onChangeText={setKpiHours}
                  placeholder="40"
                  placeholderTextColor="#8E8E93"
                  keyboardType="decimal-pad"
                />
                
                <Text style={styles.inputLabel}>Demos Done This Week</Text>
                <TextInput
                  style={styles.input}
                  value={kpiDemos}
                  onChangeText={setKpiDemos}
                  placeholder="5"
                  placeholderTextColor="#8E8E93"
                  keyboardType="number-pad"
                />
                
                <TouchableOpacity style={styles.submitButton} onPress={handleSubmitKPI}>
                  <Ionicons name="checkmark-circle" size={24} color="#FFF" />
                  <Text style={styles.submitButtonText}>Submit KPIs</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      </WebModal>

      {/* Add Member Modal */}
      <WebModal visible={showAddMember} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add Team Member</Text>
              <TouchableOpacity onPress={() => setShowAddMember(false)}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            <ScrollView style={styles.modalBody}>
              <Text style={styles.inputLabel}>First Name *</Text>
              <TextInput
                style={styles.input}
                value={newMember.first_name}
                onChangeText={(text) => setNewMember({...newMember, first_name: text})}
                placeholder="John"
                placeholderTextColor="#8E8E93"
              />
              
              <Text style={styles.inputLabel}>Last Name</Text>
              <TextInput
                style={styles.input}
                value={newMember.last_name}
                onChangeText={(text) => setNewMember({...newMember, last_name: text})}
                placeholder="Doe"
                placeholderTextColor="#8E8E93"
              />
              
              <Text style={styles.inputLabel}>Email *</Text>
              <TextInput
                style={styles.input}
                value={newMember.email}
                onChangeText={(text) => setNewMember({...newMember, email: text})}
                placeholder="john@company.com"
                placeholderTextColor="#8E8E93"
                keyboardType="email-address"
                autoCapitalize="none"
              />
              
              <Text style={styles.inputLabel}>Phone</Text>
              <TextInput
                style={styles.input}
                value={newMember.phone}
                onChangeText={(text) => setNewMember({...newMember, phone: text})}
                placeholder="+1 555 123 4567"
                placeholderTextColor="#8E8E93"
                keyboardType="phone-pad"
              />
              
              <Text style={styles.inputLabel}>Role</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.roleSelector}>
                {['partner', 'reseller', 'support', 'billing', 'admin', 'dev', 'sales', 'csm'].map((role) => (
                  <TouchableOpacity
                    key={role}
                    style={[
                      styles.roleSelectorItem,
                      newMember.role === role && { backgroundColor: ROLE_COLORS[role], borderColor: ROLE_COLORS[role] }
                    ]}
                    onPress={() => setNewMember({...newMember, role})}
                  >
                    <Text style={[
                      styles.roleSelectorText,
                      newMember.role === role && { color: '#FFF' }
                    ]}>
                      {role.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
              
              <Text style={styles.inputLabel}>Title/Position</Text>
              <TextInput
                style={styles.input}
                value={newMember.title}
                onChangeText={(text) => setNewMember({...newMember, title: text})}
                placeholder="Sales Manager"
                placeholderTextColor="#8E8E93"
              />
              
              {(newMember.role === 'partner' || newMember.role === 'reseller') && (
                <>
                  <Text style={styles.inputLabel}>Company Name</Text>
                  <TextInput
                    style={styles.input}
                    value={newMember.company_name}
                    onChangeText={(text) => setNewMember({...newMember, company_name: text})}
                    placeholder="Partner Company LLC"
                    placeholderTextColor="#8E8E93"
                  />
                  
                  <Text style={styles.inputLabel}>Commission %</Text>
                  <TextInput
                    style={styles.input}
                    value={newMember.commission_percent.toString()}
                    onChangeText={(text) => setNewMember({...newMember, commission_percent: parseFloat(text) || 0})}
                    placeholder="10"
                    placeholderTextColor="#8E8E93"
                    keyboardType="decimal-pad"
                  />
                </>
              )}
            </ScrollView>
            
            <TouchableOpacity style={styles.submitButton} onPress={handleAddMember}>
              <Ionicons name="person-add" size={20} color="#FFF" />
              <Text style={styles.submitButtonText}>Add Member</Text>
            </TouchableOpacity>
          </View>
        </View>
      </WebModal>

      {/* Member Detail Modal */}
      <WebModal visible={showMemberDetail} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Member Profile</Text>
              <TouchableOpacity onPress={() => setShowMemberDetail(false)}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            {selectedMember && (
              <ScrollView style={styles.modalBody}>
                <View style={styles.profileHeader}>
                  <View style={[styles.profileAvatar, { backgroundColor: ROLE_COLORS[selectedMember.role] + '30' }]}>
                    <Text style={[styles.profileAvatarText, { color: ROLE_COLORS[selectedMember.role] }]}>
                      {(selectedMember.first_name || selectedMember.name || '?')[0]}{(selectedMember.last_name || '')[0] || ''}
                    </Text>
                  </View>
                  <Text style={styles.profileName}>{selectedMember.first_name || selectedMember.name || 'Unknown'} {selectedMember.last_name || ''}</Text>
                  <Text style={styles.profileTitle}>{selectedMember.title || selectedMember.role_label}</Text>
                  {selectedMember.company_name && (
                    <Text style={styles.profileCompany}>{selectedMember.company_name}</Text>
                  )}
                </View>
                
                <View style={styles.profileSection}>
                  <Text style={styles.profileSectionTitle}>Contact</Text>
                  <View style={styles.profileRow}>
                    <Ionicons name="mail" size={18} color="#8E8E93" />
                    <Text style={styles.profileRowText}>{selectedMember.email}</Text>
                  </View>
                  {selectedMember.phone && (
                    <View style={styles.profileRow}>
                      <Ionicons name="call" size={18} color="#8E8E93" />
                      <Text style={styles.profileRowText}>{selectedMember.phone}</Text>
                    </View>
                  )}
                </View>
                
                <View style={styles.profileSection}>
                  <Text style={styles.profileSectionTitle}>Performance</Text>
                  <View style={styles.profileMetricsGrid}>
                    <View style={styles.profileMetric}>
                      <Text style={styles.profileMetricValue}>{formatCurrency(selectedMember.metrics.total_revenue)}</Text>
                      <Text style={styles.profileMetricLabel}>Revenue</Text>
                    </View>
                    <View style={styles.profileMetric}>
                      <Text style={styles.profileMetricValue}>{selectedMember.metrics.quotes_sent}</Text>
                      <Text style={styles.profileMetricLabel}>Quotes Sent</Text>
                    </View>
                    <View style={styles.profileMetric}>
                      <Text style={styles.profileMetricValue}>{selectedMember.metrics.quotes_accepted}</Text>
                      <Text style={styles.profileMetricLabel}>Deals Closed</Text>
                    </View>
                    <View style={styles.profileMetric}>
                      <Text style={styles.profileMetricValue}>{formatCurrency(selectedMember.metrics.avg_deal_size)}</Text>
                      <Text style={styles.profileMetricLabel}>Avg Deal Size</Text>
                    </View>
                    <View style={styles.profileMetric}>
                      <Text style={styles.profileMetricValue}>{selectedMember.metrics.avg_days_to_close || '-'}</Text>
                      <Text style={styles.profileMetricLabel}>Avg Days to Close</Text>
                    </View>
                    <View style={styles.profileMetric}>
                      <Text style={styles.profileMetricValue}>{selectedMember.metrics.avg_discount_percent}%</Text>
                      <Text style={styles.profileMetricLabel}>Avg Discount</Text>
                    </View>
                  </View>
                </View>
                
                {selectedMember.commission_percent !== undefined && selectedMember.commission_percent > 0 && (
                  <View style={styles.profileSection}>
                    <Text style={styles.profileSectionTitle}>Commission</Text>
                    <View style={styles.commissionCard}>
                      <View>
                        <Text style={styles.commissionRate}>{selectedMember.commission_percent}%</Text>
                        <Text style={styles.commissionLabel}>Commission Rate</Text>
                      </View>
                      <View>
                        <Text style={[styles.commissionRate, { color: '#34C759' }]}>
                          {formatCurrency(selectedMember.metrics.total_commission_earned)}
                        </Text>
                        <Text style={styles.commissionLabel}>Total Earned</Text>
                      </View>
                    </View>
                  </View>
                )}
              </ScrollView>
            )}
          </View>
        </View>
      </WebModal>
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
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    width: 40,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    gap: 6,
  },
  activeTab: {
    borderBottomWidth: 2,
    borderBottomColor: '#007AFF',
  },
  tabText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  activeTabText: {
    color: '#007AFF',
    fontWeight: '600',
  },
  content: {
    flex: 1,
  },
  tabContent: {
    padding: 16,
    paddingBottom: 100,
  },
  statsContainer: {
    marginBottom: 16,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 4,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    marginBottom: 12,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 16,
    color: '#FFF',
  },
  roleFilterContainer: {
    marginBottom: 16,
    marginHorizontal: -16,
  },
  roleFilterContent: {
    paddingHorizontal: 16,
    gap: 8,
    flexDirection: 'row',
  },
  roleChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
    gap: 6,
    marginRight: 8,
  },
  roleChipActive: {
    backgroundColor: '#007AFF',
  },
  roleChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  roleChipTextActive: {
    color: '#FFF',
  },
  memberCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  memberHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  avatarText: {
    fontSize: 16,
    fontWeight: '600',
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  memberTitle: {
    fontSize: 14,
    color: '#8E8E93',
  },
  memberCompany: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  memberBadges: {
    alignItems: 'flex-end',
    gap: 4,
  },
  roleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  mvpBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFD700',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 4,
  },
  mvpBadgeText: {
    fontSize: 14,
    fontWeight: '800',
    color: '#000',
  },
  rankBadgeLarge: {
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  rankSilverBg: {
    backgroundColor: '#C0C0C0',
  },
  rankBronzeBg: {
    backgroundColor: '#CD7F32',
  },
  rankBadgeText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFF',
  },
  earningsHighlight: {
    fontSize: 20,
  },
  scoreBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreText: {
    fontSize: 12,
    fontWeight: '700',
  },
  memberMetrics: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    paddingTop: 12,
  },
  memberFooter: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
    paddingTop: 12,
    marginTop: 12,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
  },
  metricItem: {
    flex: 1,
    alignItems: 'center',
  },
  metricValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  metricLabel: {
    fontSize: 10,
    color: '#8E8E93',
    marginTop: 2,
  },
  sectionHeader: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#FFF',
  },
  sectionSubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 4,
  },
  metricToggle: {
    flexDirection: 'row',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    padding: 4,
    marginBottom: 16,
  },
  metricButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  metricButtonActive: {
    backgroundColor: '#007AFF',
  },
  metricButtonText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#8E8E93',
  },
  metricButtonTextActive: {
    color: '#FFF',
  },
  leaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  rankBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  rankGold: {
    backgroundColor: '#FFD700',
  },
  rankSilver: {
    backgroundColor: '#C0C0C0',
  },
  rankBronze: {
    backgroundColor: '#CD7F32',
  },
  rankText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#000',
  },
  leaderInfo: {
    flex: 1,
    marginLeft: 8,
  },
  leaderName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  leaderRole: {
    fontSize: 12,
    color: '#8E8E93',
  },
  leaderValue: {
    alignItems: 'flex-end',
  },
  leaderValueText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#34C759',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 16,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  modalBody: {
    padding: 16,
  },
  inputLabel: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  roleSelector: {
    flexDirection: 'row',
    marginVertical: 8,
  },
  roleSelectorItem: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2C2C2E',
    marginRight: 8,
  },
  roleSelectorText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#8E8E93',
  },
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    margin: 16,
    gap: 8,
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  profileHeader: {
    alignItems: 'center',
    paddingVertical: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  profileAvatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  profileAvatarText: {
    fontSize: 28,
    fontWeight: '600',
  },
  profileName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFF',
  },
  profileTitle: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 4,
  },
  profileCompany: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 2,
  },
  profileSection: {
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  profileSectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 12,
  },
  profileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 8,
  },
  profileRowText: {
    fontSize: 16,
    color: '#FFF',
  },
  profileMetricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  profileMetric: {
    width: '30%',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 12,
    alignItems: 'center',
  },
  profileMetricValue: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
  },
  profileMetricLabel: {
    fontSize: 10,
    color: '#8E8E93',
    marginTop: 4,
    textAlign: 'center',
  },
  commissionCard: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
  },
  commissionRate: {
    fontSize: 28,
    fontWeight: '700',
    color: '#5856D6',
    textAlign: 'center',
  },
  commissionLabel: {
    fontSize: 12,
    color: '#8E8E93',
    textAlign: 'center',
    marginTop: 4,
  },
  // Efficiency Tab Styles
  tabBarScroll: {
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
    maxHeight: 50,
    flexGrow: 0,
    flexShrink: 0,
  },
  tabBarContainer: {
    height: 50,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  tabBarContent: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
  },
  efficiencyHeader: {
    alignItems: 'center',
    paddingVertical: 24,
    marginBottom: 16,
  },
  efficiencyTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 12,
  },
  efficiencySubtitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 4,
  },
  efficiencyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 10,
  },
  trophyContainer: {
    width: 44,
    alignItems: 'center',
    marginRight: 8,
  },
  rankCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#2C2C2E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankNumber: {
    fontSize: 14,
    fontWeight: '700',
    color: '#8E8E93',
  },
  efficiencyInfo: {
    flex: 1,
    marginLeft: 8,
  },
  efficiencyName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  efficiencyStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
  },
  efficiencyStat: {
    fontSize: 13,
    color: '#8E8E93',
  },
  efficiencyDot: {
    fontSize: 13,
    color: '#8E8E93',
    marginHorizontal: 6,
  },
  earningsContainer: {
    alignItems: 'flex-end',
  },
  earningsValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#34C759',
  },
  earningsLabel: {
    fontSize: 12,
    color: '#8E8E93',
  },
  inputKPIButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    gap: 8,
  },
  inputKPIButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
  },
  // KPI Modal Styles
  kpiMemberInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  kpiMemberName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
    marginLeft: 12,
  },
  kpiMemberRole: {
    fontSize: 14,
    color: '#8E8E93',
    marginLeft: 12,
  },
});
