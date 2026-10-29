#define SCALP_MODE false
#define DEFAULT_TAG "Mark2_Trend_10_30"
// Tester-only strategy port. It cannot run on a broker account chart.
#property strict
#property version "1.00"
input string SymbolsToTest="EURUSD,GBPUSD,XAUUSD";
input string ResultTag=DEFAULT_TAG;
input int PollSeconds=10;
input double TargetEquity=0;
const ulong JarvisMagic=76251026;
string assets[];
datetime processed[],lastPoll=0;
double peak=0,dayBase=0,lastClosedPnl=0;
long day=-1;
int dailyEntries=0;
bool halted=false;
ulong closeAttempt=0;
datetime firstTick=0,lastTick=0;
long signalChecks=0,signals=0,minLotRejected=0,spreadRejected=0;

double Avg(const MqlRates &r[],int end,int count)
{
   if(end<count)return 0;
   double total=0;for(int i=end-count;i<end;i++)total+=r[i].close;
   return total/count;
}
bool Cross(const MqlRates &r[],int n)
{
   return n>=31 && Avg(r,n-1,10)<=Avg(r,n-1,30) && Avg(r,n,10)>Avg(r,n,30);
}
double RiskLots(double budget,double loss,double minimum,double step,double maximum)
{
   if(budget<=0 || loss<=0 || minimum<=0 || step<=0 || maximum<minimum)return 0;
   double cap=MathMin(budget/loss,maximum);
   if(cap+1e-12<minimum)return 0;
   double lots=minimum+MathFloor((cap-minimum)/step+1e-10)*step;
   lots=NormalizeDouble(lots,8);
   if(lots*loss>budget+1e-8)return 0;
   return lots;
}
ENUM_ORDER_TYPE_FILLING Filling(string symbol)
{
   long mode=SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE);
   if((mode&SYMBOL_FILLING_IOC)!=0)return ORDER_FILLING_IOC;
   if((mode&SYMBOL_FILLING_FOK)!=0)return ORDER_FILLING_FOK;
   return ORDER_FILLING_RETURN;
}
bool SelfTest()
{
   MqlRates r[];ArrayResize(r,65);
   for(int i=0;i<65;i++)r[i].close=1;
   if(Cross(r,65))return false;
   r[64].close=1.00001;
   if(!Cross(r,65))return false;
   if(MathAbs(RiskLots(4.5,40,.01,.01,100)-.11)>1e-8)return false;
   if(RiskLots(.5,100,.01,.01,100)!=0)return false;
   if(MathAbs(RiskLots(1000,1,.01,.01,.25)-.25)>1e-8)return false;
   return true;
}
int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))return INIT_FAILED;
   if(!SelfTest()){Print("JARVIS SELF TEST FAILED");return INIT_FAILED;}
   int count=StringSplit(SymbolsToTest,',',assets);
   if(count<1 || count>10 || PollSeconds<1)return INIT_PARAMETERS_INCORRECT;
   ArrayResize(processed,count);ArrayInitialize(processed,0);
   for(int i=0;i<count;i++)
   {
      if(!SymbolSelect(assets[i],true))return INIT_FAILED;
      MqlRates warm[];
      CopyRates(assets[i],PERIOD_M1,0,70,warm);
      CopyRates(assets[i],PERIOD_M5,0,70,warm);
      CopyRates(assets[i],PERIOD_H1,0,70,warm);
   }
   peak=AccountInfoDouble(ACCOUNT_EQUITY);
   Print("JARVIS tester only; self tests passed; profile=",SCALP_MODE," symbols=",SymbolsToTest);
   return INIT_SUCCEEDED;
}
void ManageTimedExit(datetime now)
{
   if(!SCALP_MODE)return;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || (ulong)PositionGetInteger(POSITION_MAGIC)!=JarvisMagic)continue;
      if(now-(datetime)PositionGetInteger(POSITION_TIME)<180 || closeAttempt==ticket)continue;
      string symbol=PositionGetString(POSITION_SYMBOL);MqlTick q;
      if(!SymbolInfoTick(symbol,q) || now-q.time>10)continue;
      MqlTradeRequest request={};MqlTradeCheckResult checked={};MqlTradeResult result={};
      request.action=TRADE_ACTION_DEAL;request.position=ticket;request.symbol=symbol;
      request.volume=PositionGetDouble(POSITION_VOLUME);request.type=ORDER_TYPE_SELL;
      request.price=q.bid;request.magic=JarvisMagic;request.deviation=10;
      request.type_filling=Filling(symbol);request.comment="JARVIS test time exit";
      if(!OrderCheck(request,checked) || checked.retcode!=0)continue;
      closeAttempt=ticket;
      if(!OrderSend(request,result) || result.retcode!=TRADE_RETCODE_DONE)halted=true;
   }
}
void CheckSymbol(string symbol,int index,datetime now,double equity)
{
   long mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
   if(mode!=SYMBOL_TRADE_MODE_FULL && mode!=SYMBOL_TRADE_MODE_LONGONLY)return;
   if(PositionSelect(symbol))return;
   MqlTick q;if(!SymbolInfoTick(symbol,q) || now-q.time>90 || q.time>now+10 || q.ask<=q.bid)return;
   MqlRates r[],trend[];ArraySetAsSeries(r,false);ArraySetAsSeries(trend,false);
   ENUM_TIMEFRAMES frame=SCALP_MODE?PERIOD_M1:PERIOD_M5;
   int need=SCALP_MODE?35:65;
   int n=CopyRates(symbol,frame,1,need,r);
   if(n!=need)return;
   datetime bar=r[n-1].time;
   int window=SCALP_MODE?20:90;
   if(now-(bar+PeriodSeconds(frame))>window || bar+PeriodSeconds(frame)>now+10 || processed[index]==bar)return;
   signalChecks++;
   bool entry=false;
   if(SCALP_MODE)
   {
      double top=r[n-6].high;for(int j=n-5;j<n-1;j++)top=MathMax(top,r[j].high);
      if(r[n-1].close<=top || r[n-1].close<=r[n-1].open)return;
      int h=CopyRates(symbol,PERIOD_M5,1,30,trend);
      if(h<30 || Avg(trend,h,5)<=Avg(trend,h,20) || trend[h-1].close<=Avg(trend,h,20))return;
      entry=true;
   }
   else
   {
      if(!Cross(r,n))return;
      int h=CopyRates(symbol,PERIOD_H1,1,55,trend);
      if(h<55 || trend[h-1].close<=Avg(trend,h,50))return;
      entry=true;
   }
   if(!entry)return;
   signals++;
   double atr=0;
   for(int j=n-14;j<n;j++)atr+=MathMax(r[j].high-r[j].low,MathMax(MathAbs(r[j].high-r[j-1].close),MathAbs(r[j].low-r[j-1].close)));
   atr/=14;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT),spread=q.ask-q.bid;
   double distance=MathMax((SCALP_MODE?1.2:2.0)*atr,MathMax((SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL)+5)*point+spread,(SCALP_MODE?15:30)*point));
   if(spread>distance*(SCALP_MODE?.1:.15)){spreadRejected++;return;}
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   double stop=NormalizeDouble(q.ask-distance,digits),take=NormalizeDouble(q.ask+distance*(SCALP_MODE?1.2:1.5),digits);
   double loss=0;if(!OrderCalcProfit(ORDER_TYPE_BUY,symbol,1.,q.ask,stop,loss) || loss>=0)return;
   double openRisk=0;
   for(int j=PositionsTotal()-1;j>=0;j--)
   {
      if(PositionGetTicket(j)==0)return;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=JarvisMagic)return;
      double sl=PositionGetDouble(POSITION_SL),estimate=0;if(sl<=0)return;
      ENUM_ORDER_TYPE side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
      if(!OrderCalcProfit(side,PositionGetString(POSITION_SYMBOL),PositionGetDouble(POSITION_VOLUME),PositionGetDouble(POSITION_PRICE_OPEN),sl,estimate))return;
      openRisk+=MathMax(0.,-estimate);
   }
   double fraction=SCALP_MODE?.0025:((lastClosedPnl<0 || equity<=peak*.98)?.0025:.005);
   double budget=MathMin(equity*fraction,MathMin(SCALP_MODE?2.5:5.,10.-openRisk));
   double volume=RiskLots(budget*.9,-loss,SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN),SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP),SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX));
   if(volume<=0){minLotRejected++;return;}
   double exact=0,margin=0;
   if(!OrderCalcProfit(ORDER_TYPE_BUY,symbol,volume,q.ask,stop,exact) || exact>=0 || -exact>budget*.9+1e-8)return;
   if(!OrderCalcMargin(ORDER_TYPE_BUY,symbol,volume,q.ask,margin) || margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)*.2)return;
   MqlTradeRequest request={};MqlTradeCheckResult checked={};MqlTradeResult result={};
   request.action=TRADE_ACTION_DEAL;request.symbol=symbol;request.volume=volume;request.type=ORDER_TYPE_BUY;
   request.price=q.ask;request.sl=stop;request.tp=take;request.magic=JarvisMagic;request.deviation=10;
   request.type_time=ORDER_TIME_GTC;request.type_filling=Filling(symbol);request.comment="JARVIS tester only";
   if(!OrderCheck(request,checked) || checked.retcode!=0)return;
   processed[index]=bar;dailyEntries++;
   if(!OrderSend(request,result) || result.retcode!=TRADE_RETCODE_DONE)halted=true;
}
void OnTick()
{
   if(!MQLInfoInteger(MQL_TESTER))return;
   datetime now=TimeCurrent();if(firstTick==0)firstTick=now;lastTick=now;
   if(now-lastPoll<PollSeconds)return;lastPoll=now;
   ManageTimedExit(now);
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);peak=MathMax(peak,equity);
   long today=((long)now-7200)/86400;
   if(today!=day){day=today;dayBase=MathMax(AccountInfoDouble(ACCOUNT_BALANCE),equity);dailyEntries=0;}
   if(equity<=dayBase*.98 || equity<=peak*.95)halted=true;
   if(halted || (TargetEquity>0 && AccountInfoDouble(ACCOUNT_BALANCE)>=TargetEquity && PositionsTotal()==0))return;
   for(int i=0;i<ArraySize(assets);i++)
   {
      if(dailyEntries>=(SCALP_MODE?6:3) || PositionsTotal()>=(SCALP_MODE?1:2))break;
      CheckSymbol(assets[i],i,now,AccountInfoDouble(ACCOUNT_EQUITY));
   }
}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))return;
   if((ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=JarvisMagic)return;
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
      lastClosedPnl=HistoryDealGetDouble(trans.deal,DEAL_PROFIT)+HistoryDealGetDouble(trans.deal,DEAL_COMMISSION)+HistoryDealGetDouble(trans.deal,DEAL_SWAP)+HistoryDealGetDouble(trans.deal,DEAL_FEE);
}
double OnTester()
{
   FolderCreate("JARVIS_MARK2_Tests",FILE_COMMON);
   string name="JARVIS_MARK2_Tests\\"+ResultTag;
   int f=FileOpen(name+".json",FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(f!=INVALID_HANDLE)
   {
      string json=StringFormat("{\"tester_only\":true,\"profile\":\"%s\",\"symbols\":\"%s\",\"initial_deposit\":%.2f,\"net_profit\":%.2f,\"profit_factor\":%.6f,\"trades\":%.0f,\"equity_drawdown_pct\":%.6f,\"expected_payoff\":%.6f,\"final_balance\":%.2f,\"risk_latched\":%s,\"first_tick\":\"%s\",\"last_tick\":\"%s\",\"signal_checks\":%I64d,\"signals\":%I64d,\"minimum_lot_rejections\":%I64d,\"spread_rejections\":%I64d}",ResultTag,SymbolsToTest,TesterStatistics(STAT_INITIAL_DEPOSIT),TesterStatistics(STAT_PROFIT),TesterStatistics(STAT_PROFIT_FACTOR),TesterStatistics(STAT_TRADES),TesterStatistics(STAT_EQUITY_DDREL_PERCENT),TesterStatistics(STAT_EXPECTED_PAYOFF),AccountInfoDouble(ACCOUNT_BALANCE),halted?"true":"false",TimeToString(firstTick,TIME_DATE|TIME_SECONDS),TimeToString(lastTick,TIME_DATE|TIME_SECONDS),signalChecks,signals,minLotRejected,spreadRejected);
      FileWriteString(f,json);FileClose(f);Print("JARVIS RESULT ",json);
   }
   f=FileOpen(name+"-deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(f!=INVALID_HANDLE && HistorySelect(0,TimeCurrent()+86400))
   {
      FileWrite(f,"ticket","time","symbol","entry","volume","price","profit","commission","swap","fee");
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong deal=HistoryDealGetTicket(i);if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=JarvisMagic)continue;
         FileWrite(f,deal,TimeToString((datetime)HistoryDealGetInteger(deal,DEAL_TIME),TIME_DATE|TIME_SECONDS),HistoryDealGetString(deal,DEAL_SYMBOL),HistoryDealGetInteger(deal,DEAL_ENTRY),HistoryDealGetDouble(deal,DEAL_VOLUME),HistoryDealGetDouble(deal,DEAL_PRICE),HistoryDealGetDouble(deal,DEAL_PROFIT),HistoryDealGetDouble(deal,DEAL_COMMISSION),HistoryDealGetDouble(deal,DEAL_SWAP),HistoryDealGetDouble(deal,DEAL_FEE));
      }
      FileClose(f);
   }
   return TesterStatistics(STAT_PROFIT);
}
