import React, { useState, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { useThemeStore } from '../../store/themeStore';
interface MonthlyData {
  month: number;
  year: number;
  monthName: string;
  newCustomers: number;
  totalCustomers: number;
  grossRevenue: number;
  commissions: number;
  netProfit: number;
  bonusPool: number;
  companyRetained: number;
}

interface SalespersonData {
  month: number;
  year: number;
  monthName: string;
  newSales: number;
  totalCustomers: number;
  monthlyCommission: number;
  cumulativeEarnings: number;
}

interface YearSummary {
  year: number;
  totalRevenue: number;
  totalCommissions: number;
  totalBonusPool: number;
  totalRetained: number;
  endingCustomers: number;
  endingMRR: number;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const FORECAST_PERIODS = [
  { label: '1 Year', months: 12 },
  { label: '2 Years', months: 24 },
  { label: '3 Years', months: 36 },
];

// Input Field Component - defined outside to prevent re-renders
const InputField = React.memo(({ label, value, onChangeText, suffix }: {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  suffix?: string;
}) => (
  <View style={inputStyles.inputGroup}>
    <Text style={inputStyles.inputLabel}>{label}</Text>
    <View style={inputStyles.inputWrapper}>
      <TextInput
        style={inputStyles.input}
        value={value}
        onChangeText={onChangeText}
        keyboardType="numeric"
        placeholderTextColor="#8E8E93"
        returnKeyType="done"
        selectTextOnFocus
      />
      {suffix && <Text style={inputStyles.inputSuffix}>{suffix}</Text>}
    </View>
  </View>
));

const inputStyles = StyleSheet.create({
  inputGroup: {
    flex: 1,
  },
  inputLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginBottom: 6,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 8,
    paddingHorizontal: 12,
    height: 44,
  },
  input: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  inputSuffix: {
    color: '#8E8E93',
    fontSize: 14,
    marginLeft: 4,
  },
});

export default function ForecastingScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  
  // Input parameters
  const [salespeople, setSalespeople] = useState('10');
  const [salesPerPerson, setSalesPerPerson] = useState('10');
  const [avgPrice, setAvgPrice] = useState('100');
  const [commissionRate, setCommissionRate] = useState('25');
  const [bonusPoolRate, setBonusPoolRate] = useState('10');
  const [churnRate, setChurnRate] = useState('5'); // Monthly churn %
  
  const [activeTab, setActiveTab] = useState<'company' | 'sales' | 'bonus'>('company');
  const [forecastPeriod, setForecastPeriod] = useState(12); // months

  // Memoized callbacks to prevent re-renders
  const handleSalespeopleChange = useCallback((text: string) => setSalespeople(text), []);
  const handleSalesPerPersonChange = useCallback((text: string) => setSalesPerPerson(text), []);
  const handleAvgPriceChange = useCallback((text: string) => setAvgPrice(text), []);
  const handleCommissionRateChange = useCallback((text: string) => setCommissionRate(text), []);
  const handleBonusPoolRateChange = useCallback((text: string) => setBonusPoolRate(text), []);
  const handleChurnRateChange = useCallback((text: string) => setChurnRate(text), []);

  // Parse inputs
  const numSalespeople = parseInt(salespeople) || 0;
  const numSalesPerPerson = parseInt(salesPerPerson) || 0;
  const pricePerUser = parseFloat(avgPrice) || 0;
  const commissionPct = parseFloat(commissionRate) / 100 || 0;
  const bonusPct = parseFloat(bonusPoolRate) / 100 || 0;
  const monthlyChurn = parseFloat(churnRate) / 100 || 0;

  // Calculate monthly projections for selected period
  const monthlyProjections = useMemo(() => {
    const data: MonthlyData[] = [];
    let totalCustomers = 0;
    
    for (let i = 1; i <= forecastPeriod; i++) {
      const year = Math.ceil(i / 12);
      const month = ((i - 1) % 12) + 1;
      
      // New customers this month
      const newCustomers = numSalespeople * numSalesPerPerson;
      
      // Apply churn to existing customers
      const churnedCustomers = Math.floor(totalCustomers * monthlyChurn);
      totalCustomers = totalCustomers - churnedCustomers + newCustomers;
      
      // Revenue from all active customers
      const grossRevenue = totalCustomers * pricePerUser;
      
      // Commissions (residual on all revenue)
      const commissions = grossRevenue * commissionPct;
      
      // Net profit after commissions
      const netProfit = grossRevenue - commissions;
      
      // Bonus pool from profit
      const bonusPool = netProfit * bonusPct;
      
      // Company retained
      const companyRetained = netProfit - bonusPool;
      
      data.push({
        month: i,
        year,
        monthName: MONTHS[month - 1],
        newCustomers,
        totalCustomers,
        grossRevenue,
        commissions,
        netProfit,
        bonusPool,
        companyRetained,
      });
    }
    
    return data;
  }, [numSalespeople, numSalesPerPerson, pricePerUser, commissionPct, bonusPct, monthlyChurn, forecastPeriod]);

  // Calculate per-salesperson projections
  const salespersonProjections = useMemo(() => {
    const data: SalespersonData[] = [];
    let totalCustomers = 0;
    let cumulativeEarnings = 0;
    
    for (let i = 1; i <= forecastPeriod; i++) {
      const year = Math.ceil(i / 12);
      const month = ((i - 1) % 12) + 1;
      const newSales = numSalesPerPerson;
      
      // Apply churn to their existing customers
      const churnedCustomers = Math.floor(totalCustomers * monthlyChurn);
      totalCustomers = totalCustomers - churnedCustomers + newSales;
      
      // Their monthly commission (residual on their customer base)
      const monthlyCommission = totalCustomers * pricePerUser * commissionPct;
      cumulativeEarnings += monthlyCommission;
      
      data.push({
        month: i,
        year,
        monthName: MONTHS[month - 1],
        newSales,
        totalCustomers,
        monthlyCommission,
        cumulativeEarnings,
      });
    }
    
    return data;
  }, [numSalesPerPerson, pricePerUser, commissionPct, monthlyChurn, forecastPeriod]);

  // Calculate yearly summaries
  const yearlySummaries = useMemo(() => {
    const summaries: YearSummary[] = [];
    const numYears = Math.ceil(forecastPeriod / 12);
    
    for (let year = 1; year <= numYears; year++) {
      const yearData = monthlyProjections.filter(m => m.year === year);
      const lastMonth = yearData[yearData.length - 1];
      
      summaries.push({
        year,
        totalRevenue: yearData.reduce((sum, m) => sum + m.grossRevenue, 0),
        totalCommissions: yearData.reduce((sum, m) => sum + m.commissions, 0),
        totalBonusPool: yearData.reduce((sum, m) => sum + m.bonusPool, 0),
        totalRetained: yearData.reduce((sum, m) => sum + m.companyRetained, 0),
        endingCustomers: lastMonth?.totalCustomers || 0,
        endingMRR: lastMonth?.grossRevenue || 0,
      });
    }
    
    return summaries;
  }, [monthlyProjections, forecastPeriod]);

  // Grand totals across all years
  const grandTotals = useMemo(() => ({
    totalRevenue: monthlyProjections.reduce((sum, m) => sum + m.grossRevenue, 0),
    totalCommissions: monthlyProjections.reduce((sum, m) => sum + m.commissions, 0),
    totalBonusPool: monthlyProjections.reduce((sum, m) => sum + m.bonusPool, 0),
    totalRetained: monthlyProjections.reduce((sum, m) => sum + m.companyRetained, 0),
  }), [monthlyProjections]);

  // Summary stats
  const endData = monthlyProjections[monthlyProjections.length - 1];
  
  const salespersonEndData = salespersonProjections[salespersonProjections.length - 1];
  const salespersonTotalEarnings = salespersonProjections.reduce((sum, m) => sum + m.monthlyCommission, 0);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const StatCard = ({ label, value, color, subtext }: any) => (
    <View style={styles.statCard}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      {subtext && <Text style={styles.statSubtext}>{subtext}</Text>}
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Revenue Forecast</Text>
        <View style={{ width: 28 }} />
      </View>

      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView 
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="none"
        >
          {/* Input Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>FORECAST PARAMETERS</Text>
            
            {/* Time Range Selector */}
            <View style={styles.periodSelector}>
              {FORECAST_PERIODS.map((period) => (
                <TouchableOpacity
                  key={period.months}
                  style={[
                    styles.periodButton,
                    forecastPeriod === period.months && styles.periodButtonActive
                  ]}
                  onPress={() => setForecastPeriod(period.months)}
                  data-testid={`period-${period.months}`}
                >
                  <Text style={[
                    styles.periodButtonText,
                    forecastPeriod === period.months && styles.periodButtonTextActive
                  ]}>
                    {period.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            
            <View style={styles.inputRow}>
              <InputField
                label="Salespeople"
                value={salespeople}
                onChangeText={handleSalespeopleChange}
              />
              <InputField
                label="Sales/Person/Mo"
                value={salesPerPerson}
                onChangeText={handleSalesPerPersonChange}
              />
            </View>
            
            <View style={styles.inputRow}>
              <InputField
                label="Avg Price"
                value={avgPrice}
                onChangeText={handleAvgPriceChange}
                suffix="$/mo"
              />
              <InputField
                label="Commission"
                value={commissionRate}
                onChangeText={handleCommissionRateChange}
                suffix="%"
              />
          </View>
          
          <View style={styles.inputRow}>
            <InputField
              label="Bonus Pool"
              value={bonusPoolRate}
              onChangeText={handleBonusPoolRateChange}
              suffix="%"
            />
            <InputField
              label="Churn Rate"
              value={churnRate}
              onChangeText={handleChurnRateChange}
              suffix="%"
            />
          </View>
        </View>

        {/* Grand Totals Summary */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>{forecastPeriod / 12}-YEAR PROJECTION TOTALS</Text>
          
          <View style={styles.summaryGrid}>
            <StatCard
              label="Total Revenue"
              value={formatCurrency(grandTotals.totalRevenue)}
              color="#34C759"
            />
            <StatCard
              label="Total Commissions"
              value={formatCurrency(grandTotals.totalCommissions)}
              color="#FF9500"
            />
            <StatCard
              label="Total Bonus Pool"
              value={formatCurrency(grandTotals.totalBonusPool)}
              color="#AF52DE"
            />
            <StatCard
              label="Company Retained"
              value={formatCurrency(grandTotals.totalRetained)}
              color="#007AFF"
            />
          </View>
          
          <View style={styles.yearEndBox}>
            <Text style={styles.yearEndLabel}>End of Period Monthly Recurring Revenue</Text>
            <Text style={styles.yearEndValue}>{formatCurrency(endData?.grossRevenue || 0)}</Text>
            <Text style={styles.yearEndSubtext}>
              {endData?.totalCustomers || 0} active customers
            </Text>
          </View>
        </View>

        {/* Year-by-Year Breakdown */}
        {forecastPeriod > 12 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>YEAR-BY-YEAR BREAKDOWN</Text>
            
            {yearlySummaries.map((yearData) => (
              <View key={yearData.year} style={styles.yearBreakdownCard}>
                <View style={styles.yearBreakdownHeader}>
                  <Ionicons name="calendar" size={18} color="#C9A962" />
                  <Text style={styles.yearBreakdownTitle}>Year {yearData.year}</Text>
                  <View style={styles.yearMRRBadge}>
                    <Text style={styles.yearMRRText}>{formatCurrency(yearData.endingMRR)}/mo</Text>
                  </View>
                </View>
                
                <View style={styles.yearBreakdownStats}>
                  <View style={styles.yearStatItem}>
                    <Text style={styles.yearStatLabel}>Revenue</Text>
                    <Text style={[styles.yearStatValue, { color: '#34C759' }]}>
                      {formatCurrency(yearData.totalRevenue)}
                    </Text>
                  </View>
                  <View style={styles.yearStatItem}>
                    <Text style={styles.yearStatLabel}>Commissions</Text>
                    <Text style={[styles.yearStatValue, { color: '#FF9500' }]}>
                      {formatCurrency(yearData.totalCommissions)}
                    </Text>
                  </View>
                  <View style={styles.yearStatItem}>
                    <Text style={styles.yearStatLabel}>Retained</Text>
                    <Text style={[styles.yearStatValue, { color: '#007AFF' }]}>
                      {formatCurrency(yearData.totalRetained)}
                    </Text>
                  </View>
                  <View style={styles.yearStatItem}>
                    <Text style={styles.yearStatLabel}>Customers</Text>
                    <Text style={[styles.yearStatValue, { color: colors.text }]}>
                      {yearData.endingCustomers}
                    </Text>
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Tab Navigation */}
        <View style={styles.tabContainer}>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'company' && styles.tabActive]}
            onPress={() => setActiveTab('company')}
          >
            <Text style={[styles.tabText, activeTab === 'company' && styles.tabTextActive]}>
              Company
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'sales' && styles.tabActive]}
            onPress={() => setActiveTab('sales')}
          >
            <Text style={[styles.tabText, activeTab === 'sales' && styles.tabTextActive]}>
              Per Rep
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tab, activeTab === 'bonus' && styles.tabActive]}
            onPress={() => setActiveTab('bonus')}
          >
            <Text style={[styles.tabText, activeTab === 'bonus' && styles.tabTextActive]}>
              Bonus Pool
            </Text>
          </TouchableOpacity>
        </View>

        {/* Company View */}
        {activeTab === 'company' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>MONTHLY COMPANY REVENUE</Text>
            
            {/* Table Header */}
            <View style={styles.tableHeader}>
              <Text style={[styles.tableHeaderCell, { flex: 1 }]}>Period</Text>
              <Text style={[styles.tableHeaderCell, { flex: 0.8 }]}>Cust</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.2 }]}>Revenue</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.2 }]}>Comm</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.2 }]}>Retained</Text>
            </View>
            
            {monthlyProjections.map((m) => (
              <View key={m.month} style={styles.tableRow}>
                <Text style={[styles.tableCell, { flex: 1 }]}>
                  {forecastPeriod > 12 ? `Y${m.year} ` : ''}{m.monthName}
                </Text>
                <Text style={[styles.tableCell, { flex: 0.8 }]}>{m.totalCustomers}</Text>
                <Text style={[styles.tableCell, styles.greenText, { flex: 1.2 }]}>
                  {formatCurrency(m.grossRevenue)}
                </Text>
                <Text style={[styles.tableCell, styles.orangeText, { flex: 1.2 }]}>
                  {formatCurrency(m.commissions)}
                </Text>
                <Text style={[styles.tableCell, styles.blueText, { flex: 1.2 }]}>
                  {formatCurrency(m.companyRetained)}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Sales Rep View */}
        {activeTab === 'sales' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>PER SALESPERSON EARNINGS</Text>
            
            <View style={styles.repSummary}>
              <View style={styles.repSummaryItem}>
                <Text style={styles.repSummaryLabel}>End Monthly Comm.</Text>
                <Text style={styles.repSummaryValue}>
                  {formatCurrency(salespersonEndData?.monthlyCommission || 0)}
                </Text>
              </View>
              <View style={styles.repSummaryItem}>
                <Text style={styles.repSummaryLabel}>{forecastPeriod / 12}yr Total Earnings</Text>
                <Text style={styles.repSummaryValue}>
                  {formatCurrency(salespersonTotalEarnings)}
                </Text>
              </View>
            </View>
            
            {/* Table Header */}
            <View style={styles.tableHeader}>
              <Text style={[styles.tableHeaderCell, { flex: 1 }]}>Period</Text>
              <Text style={[styles.tableHeaderCell, { flex: 0.8 }]}>New</Text>
              <Text style={[styles.tableHeaderCell, { flex: 0.8 }]}>Total</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.2 }]}>Monthly $</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.2 }]}>Cumulative</Text>
            </View>
            
            {salespersonProjections.map((m, idx) => (
              <View key={m.month} style={styles.tableRow}>
                <Text style={[styles.tableCell, { flex: 1 }]}>
                  {forecastPeriod > 12 ? `Y${m.year} ` : ''}{m.monthName}
                </Text>
                <Text style={[styles.tableCell, { flex: 0.8 }]}>+{m.newSales}</Text>
                <Text style={[styles.tableCell, { flex: 0.8 }]}>{m.totalCustomers}</Text>
                <Text style={[styles.tableCell, styles.greenText, { flex: 1.2 }]}>
                  {formatCurrency(m.monthlyCommission)}
                </Text>
                <Text style={[styles.tableCell, styles.blueText, { flex: 1.2 }]}>
                  {formatCurrency(m.cumulativeEarnings)}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Bonus Pool View */}
        {activeTab === 'bonus' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>BONUS POOL DISTRIBUTION</Text>
            
            <View style={styles.bonusSummary}>
              <Text style={styles.bonusSummaryText}>
                {bonusPoolRate}% of net profit allocated for spiffs, bonuses, and incentives
              </Text>
              <Text style={styles.bonusTotalLabel}>{forecastPeriod / 12}-Year Total Bonus Pool</Text>
              <Text style={styles.bonusTotalValue}>{formatCurrency(grandTotals.totalBonusPool)}</Text>
              <Text style={styles.bonusPerRep}>
                ~{formatCurrency(grandTotals.totalBonusPool / (numSalespeople || 1))} per rep potential
              </Text>
            </View>
            
            {/* Table Header */}
            <View style={styles.tableHeader}>
              <Text style={[styles.tableHeaderCell, { flex: 1 }]}>Period</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.5 }]}>Net Profit</Text>
              <Text style={[styles.tableHeaderCell, { flex: 1.5 }]}>Bonus Pool</Text>
            </View>
            
            {monthlyProjections.map((m) => (
              <View key={m.month} style={styles.tableRow}>
                <Text style={[styles.tableCell, { flex: 1 }]}>
                  {forecastPeriod > 12 ? `Y${m.year} ` : ''}{m.monthName}
                </Text>
                <Text style={[styles.tableCell, { flex: 1.5 }]}>
                  {formatCurrency(m.netProfit)}
                </Text>
                <Text style={[styles.tableCell, styles.purpleText, { flex: 1.5 }]}>
                  {formatCurrency(m.bonusPool)}
                </Text>
              </View>
            ))}
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  inputRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  summaryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
  },
  statLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  statValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  statSubtext: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 2,
  },
  yearEndBox: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#34C759',
  },
  yearEndLabel: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  yearEndValue: {
    fontSize: 32,
    fontWeight: '700',
    color: '#34C759',
    marginTop: 4,
  },
  yearEndSubtext: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 4,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabActive: {
    backgroundColor: colors.surface,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.text,
  },
  tableHeader: {
    flexDirection: 'row',
    paddingVertical: 10,
    paddingHorizontal: 8,
    backgroundColor: colors.card,
    borderRadius: 8,
    marginBottom: 4,
  },
  tableHeaderCell: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textAlign: 'center',
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  tableCell: {
    fontSize: 13,
    color: colors.text,
    textAlign: 'center',
  },
  greenText: {
    color: '#34C759',
  },
  orangeText: {
    color: '#FF9500',
  },
  blueText: {
    color: '#007AFF',
  },
  purpleText: {
    color: '#AF52DE',
  },
  repSummary: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  repSummaryItem: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  repSummaryLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  repSummaryValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#34C759',
  },
  bonusSummary: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#AF52DE',
  },
  bonusSummaryText: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: 12,
  },
  bonusTotalLabel: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  bonusTotalValue: {
    fontSize: 28,
    fontWeight: '700',
    color: '#AF52DE',
    marginTop: 4,
  },
  bonusPerRep: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 8,
  },
  // Period selector styles
  periodSelector: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 10,
    padding: 4,
    marginBottom: 16,
  },
  periodButton: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
  },
  periodButtonActive: {
    backgroundColor: '#C9A962',
  },
  periodButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  periodButtonTextActive: {
    color: colors.text,
  },
  // Year breakdown card styles
  yearBreakdownCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  yearBreakdownHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  yearBreakdownTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    flex: 1,
  },
  yearMRRBadge: {
    backgroundColor: '#34C75920',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  yearMRRText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#34C759',
  },
  yearBreakdownStats: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  yearStatItem: {
    flex: 1,
    minWidth: '45%',
  },
  yearStatLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  yearStatValue: {
    fontSize: 15,
    fontWeight: '600',
  },
});
