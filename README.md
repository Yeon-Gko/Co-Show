#### 커밋하기 전에 꼭 사용하는것을 추천
```
git config commit.template .gitmessage.txt
```
#### 커밋 절차
1. git config commit.template .gitmessage.txt
   - 커밋 템플릿
3. git status 로 작업한 정보 확인
   - 이 명령어를 통해 어떤 파일이 수정되었는지, 스테이징할 파일은 무엇인지 확인할 수 있습니다.
4. git add [작업한 파일 이름]
   - 이 명령어를 통해 작업할 파일 추가 작업
6. git commit
   - 템플릿을 설정해둔 경우, 커밋 메시지 입력 시 .gitmessage.txt 템플릿이 자동으로 열리게 됩니다. 템플릿에 따라 메시지를 작성한 후 저장하고 닫으면 커밋이 완료됩니다.
8. git push origin [현재 브랜치 이름]
   - 원격 저장소에 푸시


#### 현제 브랜치 위치 정보 확인 
```
git branch
```
![스크린샷 2024-10-30 오전 12 11 03](https://github.com/user-attachments/assets/7d3aabcf-f73b-4aa2-a3f1-03b45c96e71e)
- 현제 위치 정보를 확인할수있다.


#### 원하는 브랜치로 전환 
```
git checkout [브랜치명] 
```
- 새로운 생성한 브랜치명을 넣으면 됩니다.


#### main 브랜치 최신 버전 가져오기 
```
git pull origin main
```
- 새로운 브랜치를 생성하기 전에 항상 main 브랜치를 최신 버전으로 업데이트해야 합니다
- 이는 코드 충돌을 방지하고 최신 기능/수정사항을 포함하기 위함입니다

