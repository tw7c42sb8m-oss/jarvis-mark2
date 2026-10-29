// Derived signal logic: Copyright 2023, Geraked. MIT license; see Geraked-MIT-LICENSE.txt.
// Source: https://github.com/geraked/metatrader5/blob/d3eb29c382acf715727d5cd6a0414151e821fc2d/Experts/3MACD.mq5
#property strict
#property version "1.00"
input bool ReverseSignals=true; // Retain upstream 3MACD reverse convention.
const int BuffSize=32;
int handles[3];
double M1[],M2[],M3[];
datetime lastBar=0;
int OnInit() {
    if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
    for(int i=0;i<3;i++) handles[i]=INVALID_HANDLE;
    handles[0]=iMACD(_Symbol,_Period,5,8,1,PRICE_CLOSE);
    handles[1]=iMACD(_Symbol,_Period,13,21,1,PRICE_CLOSE);
    handles[2]=iMACD(_Symbol,_Period,34,144,1,PRICE_CLOSE);
    for(int i=0;i<3;i++) if(handles[i]==INVALID_HANDLE) return INIT_FAILED;
    return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) {
    for(int i=0;i<3;i++) if(handles[i]!=INVALID_HANDLE) IndicatorRelease(handles[i]);
}
bool BuySignal() {

    if (M3[1] > 0 && M2[1] > 0 && M2[2] > 0 && M2[3] > 0 && M2[1] > M2[2] && M2[2] < M2[3]) {
        int j = 0;
        int k = 0;

        for (int i = 2; i < BuffSize - 1; i++) {
            if (M3[i] <= 0 || M3[i + 1] <= 0) return false;
            if (M2[i] <= 0 || M2[i + 1] <= 0) return false;
            if (M1[i] < 0 && M1[i + 1] > 0) {
                j = i + 1;
                break;
            }
        }

        if (j == 0) return false;

        for (int i = j; i < BuffSize - 2; i++) {
            if (M3[i] <= 0 || M3[i + 1] <= 0 || M3[i + 2] <= 0) return false;
            if (M2[i] <= 0 || M2[i + 1] <= 0 || M2[i + 2] <= 0) return false;
            if (M2[i] < M2[i + 1] && M2[i + 1] > M2[i + 2]) {
                k = i + 1;
                break;
            }
        }

        if (k == 0) return false;
    }

    else if (M3[1] > 0 && M3[2] > 0 && M3[3] > 0 && M3[1] > M3[2] && M3[2] < M3[3]) {
        int j = 0;
        int k = 0;
        int m = 0;

        for (int i = 2; i < BuffSize - 1; i++) {
            if (M3[i] <= 0 || M3[i + 1] <= 0) return false;
            if (M2[i] < 0 && M2[i + 1] > 0) {
                j = i + 1;
                break;
            }
        }

        if (j == 0) return false;

        for (int i = j; i < BuffSize - 1; i++) {
            if (M3[i] <= 0 || M3[i + 1] <= 0) return false;
            if (M2[i] <= 0 || M2[i + 1] <= 0) return false;
            if (M1[i] < 0 && M1[i + 1] > 0) {
                k = i + 1;
                break;
            }
        }

        if (k == 0) return false;

        for (int i = k; i < BuffSize - 2; i++) {
            if (M3[i] <= 0 || M3[i + 1] <= 0 || M3[i + 2] <= 0) return false;
            if (M2[i] <= 0 || M2[i + 1] <= 0 || M2[i + 2] <= 0) return false;
            if (M2[i] < M2[i + 1] && M2[i + 1] > M2[i + 2]) {
                m = i + 1;
                break;
            }
        }

        if (m == 0) return false;
    }

    else {
        return false;
    }


    return true;
}
bool SellSignal() {

    if (M3[1] < 0 && M2[1] < 0 && M2[2] < 0 && M2[3] < 0 && M2[1] < M2[2] && M2[2] > M2[3]) {
        int j = 0;
        int k = 0;

        for (int i = 2; i < BuffSize - 1; i++) {
            if (M3[i] >= 0 || M3[i + 1] >= 0) return false;
            if (M2[i] >= 0 || M2[i + 1] >= 0) return false;
            if (M1[i] > 0 && M1[i + 1] < 0) {
                j = i + 1;
                break;
            }
        }

        if (j == 0) return false;

        for (int i = j; i < BuffSize - 2; i++) {
            if (M3[i] >= 0 || M3[i + 1] >= 0 || M3[i + 2] >= 0) return false;
            if (M2[i] >= 0 || M2[i + 1] >= 0 || M2[i + 2] >= 0) return false;
            if (M2[i] > M2[i + 1] && M2[i + 1] < M2[i + 2]) {
                k = i + 1;
                break;
            }
        }

        if (k == 0) return false;
    }

    else if (M3[1] < 0 && M3[2] < 0 && M3[3] < 0 && M3[1] < M3[2] && M3[2] > M3[3]) {
        int j = 0;
        int k = 0;
        int m = 0;

        for (int i = 2; i < BuffSize - 1; i++) {
            if (M3[i] >= 0 || M3[i + 1] >= 0) return false;
            if (M2[i] > 0 && M2[i + 1] < 0) {
                j = i + 1;
                break;
            }
        }

        if (j == 0) return false;

        for (int i = j; i < BuffSize - 1; i++) {
            if (M3[i] >= 0 || M3[i + 1] >= 0) return false;
            if (M2[i] >= 0 || M2[i + 1] >= 0) return false;
            if (M1[i] > 0 && M1[i + 1] < 0) {
                k = i + 1;
                break;
            }
        }

        if (k == 0) return false;

        for (int i = k; i < BuffSize - 2; i++) {
            if (M3[i] >= 0 || M3[i + 1] >= 0 || M3[i + 2] >= 0) return false;
            if (M2[i] >= 0 || M2[i + 1] >= 0 || M2[i + 2] >= 0) return false;
            if (M2[i] > M2[i + 1] && M2[i + 1] < M2[i + 2]) {
                m = i + 1;
                break;
            }
        }

        if (m == 0) return false;
    }

    else {
        return false;
    }


    return true;
}

void OnTick() {
    if(!MQLInfoInteger(MQL_TESTER)) return;
    datetime bar=iTime(_Symbol,_Period,1);
    if(bar==0 || bar==lastBar) return;
    for(int i=0;i<3;i++) if(BarsCalculated(handles[i])<144+BuffSize) return;
    if(CopyBuffer(handles[0],0,0,BuffSize,M1)!=BuffSize) return;
    if(CopyBuffer(handles[1],0,0,BuffSize,M2)!=BuffSize) return;
    if(CopyBuffer(handles[2],0,0,BuffSize,M3)!=BuffSize) return;
    ArraySetAsSeries(M1,true); ArraySetAsSeries(M2,true); ArraySetAsSeries(M3,true);
    lastBar=bar;
    int side=BuySignal()?1:(SellSignal()?-1:0);
    if(ReverseSignals) side=-side;
    if(side!=0) PrintFormat("MARK2_SIGNAL_ONLY %s %s %s %d",_Symbol,EnumToString(_Period),TimeToString(bar),side);
}
